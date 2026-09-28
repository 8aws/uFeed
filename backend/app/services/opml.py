from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folder import Folder
from app.services.subscriptions import is_feed_url, list_subscriptions, subscribe

# --- Export ------------------------------------------------------------------


def _outline(text: str, feed_url: str, site_url: str | None) -> ET.Element:
    attrib = {"type": "rss", "text": text, "title": text, "xmlUrl": feed_url}
    if site_url:
        attrib["htmlUrl"] = site_url
    return ET.Element("outline", attrib)


async def export_opml(db: AsyncSession, user_id: uuid.UUID) -> str:
    rows = await list_subscriptions(db, user_id)
    folders = (await db.execute(select(Folder).where(Folder.user_id == user_id))).scalars().all()
    folder_names = {f.id: f.name for f in folders}

    opml = ET.Element("opml", {"version": "2.0"})
    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = "uFeed subscriptions"
    body = ET.SubElement(opml, "body")

    grouped: dict[uuid.UUID, list] = {}
    root_rows = []
    for row in rows:
        fid = row.subscription.folder_id
        if fid:
            grouped.setdefault(fid, []).append(row)
        else:
            root_rows.append(row)

    for fid, items in grouped.items():
        container = ET.SubElement(
            body,
            "outline",
            {"text": folder_names.get(fid, "Folder"), "title": folder_names.get(fid, "Folder")},
        )
        for row in items:
            title = row.subscription.custom_title or row.source.title or row.source.feed_url
            container.append(_outline(title, row.source.feed_url, row.source.site_url))

    for row in root_rows:
        title = row.subscription.custom_title or row.source.title or row.source.feed_url
        body.append(_outline(title, row.source.feed_url, row.source.site_url))

    xml = ET.tostring(opml, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml


# --- Import ------------------------------------------------------------------


async def _get_or_create_folder(db: AsyncSession, user_id: uuid.UUID, name: str) -> Folder:
    existing = (
        await db.execute(select(Folder).where(Folder.user_id == user_id, Folder.name == name))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    folder = Folder(user_id=user_id, name=name)
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


async def import_opml(
    db: AsyncSession, user_id: uuid.UUID, content: bytes, max_new: int | None = None
) -> tuple[int, int]:
    """Import subscriptions from OPML. Returns (imported, skipped)."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return 0, 0
    body = root.find("body")
    if body is None:
        return 0, 0

    imported = 0
    skipped = 0

    async def handle(outline: ET.Element, folder_id: uuid.UUID | None) -> None:
        nonlocal imported, skipped
        feed_url = outline.get("xmlUrl")
        if feed_url:
            if not is_feed_url(feed_url) or (max_new is not None and imported >= max_new):
                skipped += 1  # invalid URL, or the plan's feed limit is reached
                return
            _, created = await subscribe(db, user_id, feed_url.strip(), folder_id)
            if created:
                imported += 1
            else:
                skipped += 1
            return
        # A container outline becomes a folder (one level of nesting).
        name = outline.get("text") or outline.get("title") or "Imported"
        target = folder_id
        children = outline.findall("outline")
        if children:
            folder = await _get_or_create_folder(db, user_id, name)
            target = folder.id
            for child in children:
                await handle(child, target)

    for outline in body.findall("outline"):
        await handle(outline, None)

    return imported, skipped

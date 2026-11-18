import Flutter
import UIKit
import workmanager_apple

@main
@objc class AppDelegate: FlutterAppDelegate, FlutterImplicitEngineDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    // New-article notifications: the system wakes the app now and then to
    // check (see lib/notify/new_articles.dart). The identifier is also in
    // Info.plist (BGTaskSchedulerPermittedIdentifiers).
    WorkmanagerPlugin.setPluginRegistrantCallback { registry in
      GeneratedPluginRegistrant.register(with: registry)
    }
    WorkmanagerPlugin.registerPeriodicTask(
      withIdentifier: "es.uverse.ufeed.notify",
      earliestBeginInSeconds: NSNumber(value: 3600)
    )
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  func didInitializeImplicitFlutterEngine(_ engineBridge: FlutterImplicitEngineBridge) {
    GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)
  }
}

// iOS 27 closes apps that don't adopt the scene life cycle at launch
// (UIApplicationSceneManifest in Info.plist points here).
class SceneDelegate: FlutterSceneDelegate {}

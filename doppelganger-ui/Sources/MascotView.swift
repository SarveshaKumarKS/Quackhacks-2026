import SwiftUI
import AppKit

/// Shows the duck mascot for the current agent status, from 4 separate PNGs placed in
/// `Sources/Resources/` (bundled by SwiftPM). Falls back to an SF Symbol if an image
/// can't be loaded, so the mascot is never silently invisible.
///
/// Expected files (square, transparent background ideal):
///   duck_idle.png     → .idle           (sleeping)
///   duck_working.png  → .working        (typing)
///   duck_waiting.png  → .waitingForUser (question mark)
///   duck_done.png     → reserved for a future "completed" status
struct MascotView: View {
    var status: AgentStatus
    var size: CGFloat = 24

    private var imageName: String {
        switch status {
        case .idle:           return "duck_idle"
        case .working:        return "duck_working"
        case .waitingForUser: return "duck_waiting"
        }
    }

    var body: some View {
        Group {
            if let nsImage = MascotView.load(imageName) {
                Image(nsImage: nsImage)
                    .resizable()
                    .interpolation(.high)
                    .scaledToFit()
            } else {
                // Never blank: a tinted placeholder also tells us the image didn't load.
                Image(systemName: "bird.fill")
                    .resizable()
                    .scaledToFit()
                    .foregroundColor(.mallardGreen)
                    .opacity(0.85)
            }
        }
        .frame(width: size, height: size)
        .animation(.easeInOut(duration: 0.2), value: imageName)
    }

    /// Robust loader: tries the app's main bundle, the SwiftPM module bundle, and the
    /// copied SPM resource bundle inside the .app, then the asset-catalog name.
    private static func load(_ name: String) -> NSImage? {
        for b in [Bundle.main, Bundle.module] {
            if let url = b.url(forResource: name, withExtension: "png"),
               let img = NSImage(contentsOf: url) { return img }
        }
        if let res = Bundle.main.resourceURL?
            .appendingPathComponent("DoppelgangerOS_DoppelgangerOS.bundle")
            .appendingPathComponent(name + ".png"),
           let img = NSImage(contentsOf: res) { return img }
        return NSImage(named: name)
    }
}

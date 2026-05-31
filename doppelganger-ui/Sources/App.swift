import SwiftUI

@main
struct DoppelgangerApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    var body: some Scene {
        // We handle our window creation manually in AppDelegate to make it a transparent, 
        // borderless, and non-activating floating panel hanging beneath the notch.
        Settings {
            Text("Doppelgänger OS Settings")
                .frame(width: 300, height: 200)
        }
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Programmatically activate the background app to guarantee text input focus
        NSApp.activate(ignoringOtherApps: true)
        
        let contentView = ContentView()
        
        let window = NotchWindow(
            contentRect: NSRect(x: 0, y: 0, width: 400, height: 600), // Height of 600 accommodates the expanded panel dynamically
            styleMask: [.borderless, .nonactivatingPanel, .fullSizeContentView, .utilityWindow],
            backing: .buffered,
            defer: false
        )
        
        // Window level must float over everything (above normal menu/screensaver)
        window.level = .statusBar
        window.backgroundColor = .clear
        window.isOpaque = false
        window.hasShadow = false
        window.ignoresMouseEvents = false
        window.isMovableByWindowBackground = true // Standard AppKit property to make borderless windows draggable anywhere!
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        
        // Hide standard window decoration
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        
        window.contentView = NSHostingView(rootView: contentView)
        self.window = window
        
        // Align the window as a floating widget (top-right of the screen)
        alignWindowAsFloatingWidget()
        
        window.makeKeyAndOrderFront(nil)
        window.orderFrontRegardless()
    }
    
    func alignWindowAsFloatingWidget() {
        guard let window = self.window, let screen = NSScreen.main else { return }
        let screenFrame = screen.frame
        let windowFrame = window.frame
        
        // Compute top-right coordinates with 30 points of padding from screen edge
        let x = screenFrame.width - windowFrame.width - 30
        let y = screenFrame.height - windowFrame.height - 50 // Leaves space for the menu bar
        
        window.setFrameOrigin(NSPoint(x: x, y: y))
    }
    
    func applicationWillTerminate(_ notification: Notification) {
        // Crucial for supervisor cleanup: kill the Python child process gracefully
        ProcessSupervisor.shared.stopOrchestrator()
    }
}

class NotchWindow: NSPanel {
    override var canBecomeKey: Bool {
        return true
    }
    
    override var canBecomeMain: Bool {
        return true
    }
}


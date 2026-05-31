import SwiftUI

/// Renders one frame from a horizontal sprite sheet of 4 equal-width frames.
/// The asset `Gemini_Generated_Image_khfgaekhfgaekhfg.png` must live in
/// Sources/Resources/ so SwiftPM bundles it as a module resource.
///
/// Frame mapping:
///   0 → .idle (sleeping duck with beanie)
///   1 → .working (duck typing at keyboard)
///   2 → .waitingForUser (duck with question mark)
///   3 → unused fallback (cheering duck — reserved for a future "completed" status)
struct MascotView: View {
    var status: AgentStatus
    var size: CGFloat = 24

    private let frameCount: CGFloat = 4
    private let assetName: String = "Gemini_Generated_Image_khfgaekhfgaekhfg"

    private var frameIndex: Int {
        switch status {
        case .idle:           return 0
        case .working:        return 1
        case .waitingForUser: return 2
        }
    }

    var body: some View {
        // The sprite sheet is 4 frames wide. We render the full sheet at
        // (size * 4) wide, then shift it left by (size * frameIndex) and
        // clip to a (size × size) window to expose just the chosen frame.
        Image(assetName, bundle: .module)
            .resizable()
            .interpolation(.high)
            .aspectRatio(frameCount, contentMode: .fit) // total sheet is 4:1
            .frame(width: size * frameCount, height: size)
            .offset(x: -CGFloat(frameIndex) * size)
            .frame(width: size, height: size, alignment: .leading)
            .clipped()
            .animation(.easeInOut(duration: 0.25), value: frameIndex)
    }
}

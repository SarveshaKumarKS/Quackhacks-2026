import SwiftUI

extension Color {
    static let mallardGreen = Color(red: 0x2C / 255.0, green: 0x6A / 255.0, blue: 0x4F / 255.0)
    static let beakYellow   = Color(red: 0xF4 / 255.0, green: 0xA2 / 255.0, blue: 0x61 / 255.0)
    static let mallardGreenSoft = Color(red: 0x2C / 255.0, green: 0x6A / 255.0, blue: 0x4F / 255.0).opacity(0.18)
    static let beakYellowSoft   = Color(red: 0xF4 / 255.0, green: 0xA2 / 255.0, blue: 0x61 / 255.0).opacity(0.18)
}

struct GlassPanel: ViewModifier {
    var cornerRadius: CGFloat = 10

    func body(content: Content) -> some View {
        content
            .background(Color.white.opacity(0.05))
            .background(
                VisualEffectView(material: .hudWindow, blendingMode: .withinWindow)
            )
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .stroke(Color.white.opacity(0.08), lineWidth: 0.5)
            )
    }
}

extension View {
    func glassPanel(cornerRadius: CGFloat = 10) -> some View {
        modifier(GlassPanel(cornerRadius: cornerRadius))
    }
}

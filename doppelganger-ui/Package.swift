// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "DoppelgangerOS",
    platforms: [
        .macOS(.v14)  // Requires macOS Sonoma or newer
    ],
    products: [
        .executable(name: "DoppelgangerOS", targets: ["DoppelgangerOS"])
    ],
    dependencies: [],
    targets: [
        .executableTarget(
            name: "DoppelgangerOS",
            path: "Sources",
            resources: [
                .process("Resources")
            ],
            // Embeds the physical Info.plist directly into the Mach-O binary __info_plist segment
            // This is the absolute cleanest systems-level way to satisfy macOS TCC without an .app bundle.
            linkerSettings: [
                .unsafeFlags([
                    "-Xlinker", "-sectcreate",
                    "-Xlinker", "__TEXT",
                    "-Xlinker", "__info_plist",
                    "-Xlinker", "Info.plist"
                ])
            ]
        )
    ]
)

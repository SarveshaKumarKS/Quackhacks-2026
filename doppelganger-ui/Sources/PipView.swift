import SwiftUI

struct PipView: View {
    @State private var screenImage: NSImage? = nil
    @State private var isStreaming = false
    @State private var timer: Timer? = nil
    
    let frameUrl = URL(string: "http://localhost:8421/frame.jpg")!
    
    var body: some View {
        VStack {
            if let image = screenImage {
                Image(nsImage: image)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .cornerRadius(8)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(Color.white.opacity(0.15), lineWidth: 1)
                    )
            } else {
                VStack(spacing: 8) {
                    ProgressView()
                        .scaleEffect(0.8)
                    Text("Connecting to Clone Screen...")
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .foregroundColor(.gray)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.black.opacity(0.6))
                .cornerRadius(8)
            }
        }
        .onAppear {
            startStream()
        }
        .onDisappear {
            stopStream()
        }
    }
    
    func startStream() {
        guard !isStreaming else { return }
        isStreaming = true
        
        // Fetch a frame every 0.15s (~7 frames per second)
        timer = Timer.scheduledTimer(withTimeInterval: 0.15, repeats: true) { _ in
            fetchFrame()
        }
    }
    
    func stopStream() {
        isStreaming = false
        timer?.invalidate()
        timer = nil
    }
    
    func fetchFrame() {
        URLSession.shared.dataTask(with: frameUrl) { data, response, error in
            guard error == nil, let data = data else {
                return
            }
            
            if let newImage = NSImage(data: data) {
                DispatchQueue.main.async {
                    self.screenImage = newImage
                }
            }
        }.resume()
    }
}

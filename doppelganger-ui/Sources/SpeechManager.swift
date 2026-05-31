import Foundation

class SpeechManager: ObservableObject {
    static let shared = SpeechManager()
    
    @Published var transcription: String = ""
    @Published var isRecording: Bool = false
    @Published var permissionGranted: Bool = true
    
    private var simulationTimer: Timer?
    
    init() {
        // Zero-crash initialization: bypasses blocked native APIs in CLI mode
    }
    
    func startRecording() {
        guard !isRecording else { return }
        
        isRecording = true
        transcription = ""
        
        let demoPrompt = "Summarize Machine Learning subreddit"
        var currentIndex = 0
        
        // Simulates high-fidelity real-time typing transcription letter-by-letter
        simulationTimer = Timer.scheduledTimer(withTimeInterval: 0.06, repeats: true) { [weak self] timer in
            guard let self = self else {
                timer.invalidate()
                return
            }
            
            if !self.isRecording {
                timer.invalidate()
                return
            }
            
            if currentIndex < demoPrompt.count {
                let index = demoPrompt.index(demoPrompt.startIndex, offsetBy: currentIndex)
                self.transcription.append(demoPrompt[index])
                currentIndex += 1
            } else {
                self.isRecording = false
                timer.invalidate()
            }
        }
    }
    
    func stopRecording() {
        isRecording = false
        simulationTimer?.invalidate()
        simulationTimer = nil
    }
}

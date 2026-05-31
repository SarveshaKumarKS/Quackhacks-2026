import Foundation
import AVFoundation
import Speech

/// Real speech I/O for the notch UI:
///   - Input  (STT): live microphone transcription via SFSpeechRecognizer + AVAudioEngine.
///   - Output (TTS): spoken nudges via AVSpeechSynthesizer (native, offline, no API key).
///
/// Everything degrades gracefully: if mic/speech permission is denied or the
/// recognizer is unavailable, recording becomes a safe no-op (the user can still type),
/// and we never crash. macOS has no AVAudioSession, so none is configured here.
class SpeechManager: ObservableObject {
    static let shared = SpeechManager()

    @Published var transcription: String = ""
    @Published var isRecording: Bool = false
    @Published var permissionGranted: Bool = false

    // --- Output (TTS) ---
    private let synthesizer = AVSpeechSynthesizer()

    // --- Input (STT) ---
    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private let audioEngine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?

    init() {
        requestPermissions()
    }

    /// Ask for speech-recognition and microphone access up front (one-time TCC prompt).
    func requestPermissions() {
        SFSpeechRecognizer.requestAuthorization { status in
            DispatchQueue.main.async {
                let speechOK = (status == .authorized)
                AVCaptureDevice.requestAccess(for: .audio) { micOK in
                    DispatchQueue.main.async {
                        self.permissionGranted = speechOK && micOK
                    }
                }
            }
        }
    }

    // MARK: - Speech to text

    func startRecording() {
        guard !isRecording else { return }
        guard permissionGranted, let recognizer = recognizer, recognizer.isAvailable else {
            print("[Speech] Recognition unavailable (permission denied or recognizer offline). Type instead.")
            return
        }

        // Reset any prior session.
        task?.cancel()
        task = nil

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        self.request = request

        let input = audioEngine.inputNode
        let format = input.outputFormat(forBus: 0)
        input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
            request.append(buffer)
        }

        audioEngine.prepare()
        do {
            try audioEngine.start()
        } catch {
            print("[Speech] Failed to start audio engine: \(error)")
            input.removeTap(onBus: 0)
            return
        }

        isRecording = true
        transcription = ""

        task = recognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self = self else { return }
            if let result = result {
                DispatchQueue.main.async {
                    self.transcription = result.bestTranscription.formattedString
                }
            }
            if error != nil || (result?.isFinal ?? false) {
                self.stopRecording()
            }
        }
    }

    func stopRecording() {
        if audioEngine.isRunning {
            audioEngine.stop()
            audioEngine.inputNode.removeTap(onBus: 0)
        }
        request?.endAudio()
        task?.cancel()
        request = nil
        task = nil
        DispatchQueue.main.async {
            self.isRecording = false
        }
    }

    // MARK: - Text to speech (spoken nudges)

    /// Speak a short, natural-sounding nudge. Kept brief so nudges stay minimal.
    func speak(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        // Cap spoken length so long drafts/answers don't monologue.
        let toSpeak = String(trimmed.prefix(240))

        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking(at: .immediate)
        }
        let utterance = AVSpeechUtterance(string: toSpeak)
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        synthesizer.speak(utterance)
    }
}

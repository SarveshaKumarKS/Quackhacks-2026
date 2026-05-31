import Foundation
import AVFoundation
import Speech

/// Real speech I/O for the notch UI:
///   - Input  (STT): live microphone transcription via SFSpeechRecognizer + AVAudioEngine.
///   - Output (TTS): spoken nudges via ElevenLabs when an API key is configured in
///     orchestrator/.env, otherwise the native AVSpeechSynthesizer. ElevenLabs failures
///     (missing key, bad voice, network) fall back to the native voice automatically.
///
/// Everything degrades gracefully and never crashes. macOS has no AVAudioSession,
/// so none is configured.
class SpeechManager: ObservableObject {
    static let shared = SpeechManager()

    @Published var transcription: String = ""
    @Published var isRecording: Bool = false
    @Published var permissionGranted: Bool = false

    // --- Output (TTS) ---
    private let synthesizer = AVSpeechSynthesizer()
    private var audioPlayer: AVAudioPlayer?
    private let elevenLabsKey: String?
    private let elevenLabsVoice: String
    private let defaultVoiceId = "21m00Tcm4TlvDq8ikWAM"  // ElevenLabs "Rachel"
    private var resolvedVoiceId: String?

    // --- Input (STT) ---
    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private let audioEngine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?

    init() {
        let env = SpeechManager.loadEnv()
        let key = env["ELEVENLABS_API_KEY"] ?? ""
        // Treat empty / template placeholder as "not configured" -> native voice.
        self.elevenLabsKey = (key.isEmpty || key.contains("your-elevenlabs")) ? nil : key
        let voice = env["ELEVENLABS_VOICE_ID"] ?? ""
        self.elevenLabsVoice = voice.isEmpty ? "Rachel" : voice
        // NOTE: do NOT request Speech/Mic permission here. Requesting at launch (a)
        // pops prompts immediately and (b) hard-crashes (SIGABRT) when the usage-string
        // Info.plist isn't honored — which happens when run via `swift run` instead of a
        // real .app bundle. Permission is requested lazily on first mic use instead.
    }

    // MARK: - .env loading (orchestrator/.env on Profile A)

    private static func loadEnv() -> [String: String] {
        let fm = FileManager.default
        let cwd = fm.currentDirectoryPath
        let candidates = [
            cwd + "/orchestrator/.env",
            cwd + "/../orchestrator/.env",
            cwd + "/../../orchestrator/.env",
        ]
        for path in candidates {
            guard let content = try? String(contentsOfFile: path, encoding: .utf8) else { continue }
            var dict: [String: String] = [:]
            for rawLine in content.split(separator: "\n") {
                let line = rawLine.trimmingCharacters(in: .whitespaces)
                if line.isEmpty || line.hasPrefix("#") { continue }
                guard let eq = line.firstIndex(of: "=") else { continue }
                let k = String(line[..<eq]).trimmingCharacters(in: .whitespaces)
                var v = String(line[line.index(after: eq)...])
                if let hash = v.range(of: " #") { v = String(v[..<hash.lowerBound]) }
                v = v.trimmingCharacters(in: .whitespaces)
                if (v.hasPrefix("\"") && v.hasSuffix("\"")) || (v.hasPrefix("'") && v.hasSuffix("'")), v.count >= 2 {
                    v = String(v.dropFirst().dropLast())
                }
                dict[k] = v
            }
            return dict
        }
        return [:]
    }

    // MARK: - Permissions

    func requestPermissions(completion: ((Bool) -> Void)? = nil) {
        SFSpeechRecognizer.requestAuthorization { status in
            DispatchQueue.main.async {
                let speechOK = (status == .authorized)
                AVCaptureDevice.requestAccess(for: .audio) { micOK in
                    DispatchQueue.main.async {
                        self.permissionGranted = speechOK && micOK
                        completion?(self.permissionGranted)
                    }
                }
            }
        }
    }

    func beginRecordingWithPermissions() {
        if permissionGranted {
            startRecording()
            return
        }
        requestPermissions { [weak self] granted in
            guard let self = self else { return }
            if granted {
                self.startRecording()
            } else {
                print("[Speech] Microphone or Speech Recognition permission was not granted. Type instead.")
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

    /// Speak a short, natural-sounding nudge. ElevenLabs if configured, else native.
    func speak(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        let toSpeak = String(trimmed.prefix(240))

        // Stop any in-flight speech first.
        audioPlayer?.stop()
        if synthesizer.isSpeaking { synthesizer.stopSpeaking(at: .immediate) }

        if let key = elevenLabsKey {
            speakWithElevenLabs(toSpeak, key: key)
        } else {
            speakNative(toSpeak)
        }
    }

    private func speakNative(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        synthesizer.speak(utterance)
    }

    private func speakWithElevenLabs(_ text: String, key: String) {
        resolveVoiceId(elevenLabsVoice, key: key) { [weak self] voiceId in
            guard let self = self else { return }
            guard let url = URL(string: "https://api.elevenlabs.io/v1/text-to-speech/\(voiceId)") else {
                DispatchQueue.main.async { self.speakNative(text) }
                return
            }
            var req = URLRequest(url: url)
            req.httpMethod = "POST"
            req.setValue(key, forHTTPHeaderField: "xi-api-key")
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.setValue("audio/mpeg", forHTTPHeaderField: "Accept")
            let body: [String: Any] = [
                "text": text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": [
                    "stability": 0.35,        // lower = more emotion / variation
                    "similarity_boost": 0.8,  // keep close to the original voice
                    "style": 0.15,            // slight expressive exaggeration
                    "use_speaker_boost": true,
                ],
            ]
            req.httpBody = try? JSONSerialization.data(withJSONObject: body)

            URLSession.shared.dataTask(with: req) { [weak self] data, response, _ in
                guard let self = self else { return }
                let code = (response as? HTTPURLResponse)?.statusCode ?? -1
                if code == 200, let data = data, !data.isEmpty {
                    DispatchQueue.main.async { self.playAudio(data, fallbackText: text) }
                } else {
                    print("[Speech] ElevenLabs TTS failed (HTTP \(code)); falling back to native voice.")
                    DispatchQueue.main.async { self.speakNative(text) }
                }
            }.resume()
        }
    }

    /// Resolve a configured voice (an ID, or a name like "Jarvis") to an ElevenLabs voice_id.
    private func resolveVoiceId(_ configured: String, key: String, completion: @escaping (String) -> Void) {
        if let cached = resolvedVoiceId { completion(cached); return }
        // Already looks like an ElevenLabs ID (20-char alphanumeric)?
        if configured.count >= 18 && configured.allSatisfy({ $0.isLetter || $0.isNumber }) {
            resolvedVoiceId = configured
            completion(configured)
            return
        }
        guard let url = URL(string: "https://api.elevenlabs.io/v1/voices") else {
            completion(defaultVoiceId); return
        }
        var req = URLRequest(url: url)
        req.setValue(key, forHTTPHeaderField: "xi-api-key")
        URLSession.shared.dataTask(with: req) { [weak self] data, _, _ in
            guard let self = self else { return }
            var id = self.defaultVoiceId
            if let data = data,
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let voices = json["voices"] as? [[String: Any]],
               let match = voices.first(where: {
                   ($0["name"] as? String)?.lowercased() == configured.lowercased()
               }),
               let vid = match["voice_id"] as? String {
                id = vid
            }
            self.resolvedVoiceId = id
            completion(id)
        }.resume()
    }

    private func playAudio(_ data: Data, fallbackText: String) {
        do {
            let player = try AVAudioPlayer(data: data)
            self.audioPlayer = player  // strong reference so it isn't deallocated mid-playback
            player.prepareToPlay()
            player.play()
        } catch {
            print("[Speech] Audio playback failed: \(error); falling back to native voice.")
            speakNative(fallbackText)
        }
    }
}

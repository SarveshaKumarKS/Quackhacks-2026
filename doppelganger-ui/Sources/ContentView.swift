import SwiftUI

enum AgentStatus {
    case idle
    case working
    case waitingForUser
}

struct OrchestratorState: Codable {
    let status: String
    let nudge_message: String
    let logs: [String]
    let step_count: Int
    let pending_prompt_id: Int?
}

struct ContentView: View {
    @StateObject private var speechManager = SpeechManager.shared
    @StateObject private var supervisor = ProcessSupervisor.shared
    
    @State private var status: AgentStatus = .idle
    @State private var isExpanded: Bool = false
    @State private var promptText: String = ""
    @State private var nudgeMessage: String = ""
    @State private var pulseOpacity = 0.5
    @State private var timer: Timer? = nil
    @State private var logs: [String] = []
    @State private var stepCount: Int = 0
    @State private var pendingPromptId: Int? = nil
    @State private var isApprovalSubmitting: Bool = false
    @State private var lastSpokenMessageKey: String = ""
    
    var body: some View {
        VStack(spacing: 0) {
            // 1. The Floating Notch Pill (Resting State)
            HStack(spacing: 12) {
                // Pulse status indicator light
                Circle()
                    .fill(statusColor)
                    .frame(width: 8, height: 8)
                    .opacity(pulseOpacity)
                    .onAppear {
                        withAnimation(Animation.easeInOut(duration: 1.2).repeatForever(autoreverses: true)) {
                            pulseOpacity = 1.0
                        }
                    }
                
                Text(pillLabel)
                    .font(.system(size: 11, weight: .semibold, design: .rounded))
                    .foregroundColor(.white.opacity(0.9))
                
                Spacer()
                
                // Chevron expand/collapse toggle
                Button(action: {
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                        isExpanded.toggle()
                    }
                }) {
                    Image(systemName: isExpanded ? "chevron.up.circle.fill" : "chevron.down.circle.fill")
                        .font(.system(size: 14))
                        .foregroundColor(.white.opacity(0.6))
                }
                .buttonStyle(PlainButtonStyle())
                .help(isExpanded ? "Collapse panel" : "Expand panel")
                
                // Quit button
                Button(action: {
                    NSApplication.shared.terminate(nil)
                }) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 14))
                        .foregroundColor(.red.opacity(0.8))
                }
                .buttonStyle(PlainButtonStyle())
                .help("Quit Doppelgänger OS")
            }
            .padding(.horizontal, 16)
            .frame(height: 38)
            .background(
                VisualEffectView(material: .hudWindow, blendingMode: .withinWindow)
                    .overlay(
                        RoundedRectangle(cornerRadius: 19)
                            .stroke(Color.white.opacity(0.12), lineWidth: 1)
                    )
            )
            .clipShape(RoundedRectangle(cornerRadius: 19))
            
            // 2. The Expandable Panel containing PiP, Transcription, Logs, and Controls
            if isExpanded {
                VStack(spacing: 14) {
                    // PiP Video Feeds View
                    PipView()
                        .frame(height: 180)
                        .padding(.horizontal, 4)
                    
                    // Nudge message display if present
                    if !nudgeMessage.isEmpty {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Nudge Prompt:")
                                    .font(.system(size: 9, weight: .bold, design: .rounded))
                                    .foregroundColor(.orange.opacity(0.8))
                                Text(nudgeMessage)
                                    .font(.system(size: 11, weight: .medium, design: .rounded))
                                    .foregroundColor(Color.orange.opacity(0.95))
                            }
                            
                            Spacer()
                            
                            if status == .waitingForUser {
                                // Yes / Approve Button — sends an affirmative so the
                                // orchestrator's confirm-before-send gate proceeds.
                                Button(action: {
                                    guard !isApprovalSubmitting else { return }
                                    self.promptText = "yes"
                                    self.isApprovalSubmitting = true
                                    self.nudgeMessage = ""
                                    sendInstruction()
                                }) {
                                    Text(isApprovalSubmitting ? "Sent" : "Approve")
                                        .font(.system(size: 10, weight: .bold, design: .rounded))
                                        .foregroundColor(.white)
                                        .padding(.horizontal, 10)
                                        .padding(.vertical, 4)
                                        .background(Color.orange.opacity(isApprovalSubmitting ? 0.35 : 0.8))
                                        .cornerRadius(4)
                                }
                                .disabled(isApprovalSubmitting)
                                .buttonStyle(PlainButtonStyle())
                            }
                        }
                        .padding(.all, 8)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.orange.opacity(0.1))
                        .cornerRadius(6)
                    }
                    
                    // Console Logs Feed Component (Premium Terminal aesthetics)
                    if !logs.isEmpty {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Clone Console Logs:")
                                .font(.system(size: 9, weight: .bold, design: .rounded))
                                .foregroundColor(.white.opacity(0.5))
                            
                            ScrollView {
                                ScrollViewReader { proxy in
                                    VStack(alignment: .leading, spacing: 4) {
                                        ForEach(0..<logs.count, id: \.self) { idx in
                                            Text(logs[idx])
                                                .font(.system(size: 9, weight: .medium, design: .monospaced))
                                                .foregroundColor(logColor(logs[idx]))
                                                .frame(maxWidth: .infinity, alignment: .leading)
                                                .id(idx)
                                        }
                                    }
                                    .onAppear {
                                        proxy.scrollTo(logs.count - 1)
                                    }
                                    .onChange(of: logs) { _ in
                                        proxy.scrollTo(logs.count - 1)
                                    }
                                }
                            }
                            .frame(height: 80)
                            .padding(8)
                            .background(Color.black.opacity(0.4))
                            .cornerRadius(6)
                            .overlay(
                                RoundedRectangle(cornerRadius: 6)
                                    .stroke(Color.white.opacity(0.08), lineWidth: 1)
                            )
                        }
                        .padding(.horizontal, 4)
                    }
                    
                    // Chat and Voice transcription field
                    HStack(spacing: 8) {
                        // Microphone capture toggle
                        Button(action: {
                            if speechManager.isRecording {
                                speechManager.stopRecording()
                                self.promptText = speechManager.transcription
                            } else {
                                speechManager.startRecording()
                            }
                        }) {
                            Image(systemName: speechManager.isRecording ? "mic.fill" : "mic")
                                .font(.system(size: 13))
                                .foregroundColor(speechManager.isRecording ? .red : .white.opacity(0.8))
                                .frame(width: 28, height: 28)
                                .background(speechManager.isRecording ? Color.red.opacity(0.15) : Color.white.opacity(0.08))
                                .clipShape(Circle())
                        }
                        .buttonStyle(PlainButtonStyle())
                        
                        // Editable Input Field (Edit-Before-Send Guardrail)
                        TextField(speechManager.isRecording ? "Listening..." : "Tell the twin what to do...", text: $promptText, onCommit: {
                            sendInstruction()
                        })
                        .textFieldStyle(PlainTextFieldStyle())
                        .font(.system(size: 11, weight: .regular, design: .rounded))
                        .padding(.horizontal, 10)
                        .frame(height: 28)
                        .background(Color.black.opacity(0.3))
                        .cornerRadius(6)
                        .overlay(
                            RoundedRectangle(cornerRadius: 6)
                                .stroke(Color.white.opacity(0.1), lineWidth: 1)
                        )
                        .foregroundColor(.white)
                        
                        // Submit instruction button
                        Button(action: sendInstruction) {
                            Image(systemName: "arrow.up.circle.fill")
                                .font(.system(size: 18))
                                .foregroundColor(.blue)
                        }
                        .buttonStyle(PlainButtonStyle())
                    }
                    
                    // Subprocess Orchestrator Controls
                    HStack {
                        Text(supervisor.isOrchestratorRunning ? "Orchestrator: ACTIVE" : "Orchestrator: INACTIVE")
                            .font(.system(size: 9, weight: .semibold, design: .monospaced))
                            .foregroundColor(supervisor.isOrchestratorRunning ? .green : .red)
                        
                        Spacer()
                        
                        Button(action: {
                            if supervisor.isOrchestratorRunning {
                                supervisor.stopOrchestrator()
                            } else {
                                supervisor.startOrchestrator()
                            }
                        }) {
                            Text(supervisor.isOrchestratorRunning ? "Stop Service" : "Start Service")
                                .font(.system(size: 9, weight: .bold, design: .rounded))
                                .foregroundColor(.white)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 3)
                                .background(supervisor.isOrchestratorRunning ? Color.red.opacity(0.6) : Color.blue.opacity(0.6))
                                .cornerRadius(4)
                        }
                        .buttonStyle(PlainButtonStyle())
                    }
                    .padding(.top, 4)
                }
                .padding(.all, 12)
                .background(
                    VisualEffectView(material: .hudWindow, blendingMode: .withinWindow)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(Color.white.opacity(0.12), lineWidth: 1)
                        )
                )
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .padding(.top, 6)
                .transition(.asymmetric(
                    insertion: .opacity.combined(with: .move(edge: .top)),
                    removal: .opacity.combined(with: .move(edge: .top))
                ))
            }
        }
        .padding(.horizontal, 20)
        .frame(width: 400)
        .onAppear {
            startStatePolling()
        }
        .onDisappear {
            stopStatePolling()
        }
        // Bind incoming transcription updates to our textfield
        .onReceive(speechManager.$transcription) { text in
            if speechManager.isRecording {
                self.promptText = text
            }
        }
    }
    
    var statusColor: Color {
        switch status {
        case .idle: return Color(red: 0.4, green: 0.8, blue: 0.4) // Harmonious HSL green
        case .working: return Color(red: 0.4, green: 0.6, blue: 0.9) // Harmonious HSL blue
        case .waitingForUser: return Color(red: 0.9, green: 0.6, blue: 0.3) // Harmonious HSL orange
        }
    }
    
    var pillLabel: String {
        switch status {
        case .idle: return "Doppelgänger: Ready"
        case .working: return "Doppelgänger: Step \(stepCount) in progress..."
        case .waitingForUser: return "Doppelgänger: Action Nudge!"
        }
    }
    
    func logColor(_ text: String) -> Color {
        if text.contains("[!]") || text.contains("Error") || text.contains("failure") {
            return Color(red: 0.9, green: 0.4, blue: 0.4)
        } else if text.contains("[x]") || text.contains("Success") || text.contains("accomplished") {
            return Color(red: 0.4, green: 0.8, blue: 0.4)
        } else if text.contains("[Brain]") || text.contains("Thought") {
            return Color(red: 0.4, green: 0.6, blue: 0.9)
        } else if text.contains("[Step") {
            return Color(red: 0.9, green: 0.8, blue: 0.4)
        } else {
            return Color.white.opacity(0.8)
        }
    }
    
    func startStatePolling() {
        fetchOrchestratorState()
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
            fetchOrchestratorState()
        }
    }
    
    func stopStatePolling() {
        timer?.invalidate()
        timer = nil
    }
    
    func fetchOrchestratorState() {
        guard let url = URL(string: "http://127.0.0.1:8420/state") else { return }
        URLSession.shared.dataTask(with: url) { data, response, error in
            guard let data = data, error == nil else {
                return
            }
            do {
                let decoder = JSONDecoder()
                let stateResponse = try decoder.decode(OrchestratorState.self, from: data)
                DispatchQueue.main.async {
                    let newNudge = stateResponse.nudge_message
                    self.nudgeMessage = newNudge
                    self.logs = stateResponse.logs
                    self.stepCount = stateResponse.step_count
                    let newPromptId = stateResponse.pending_prompt_id

                    switch stateResponse.status {
                    case "working":
                        self.status = .working
                    case "waiting_for_user":
                        self.status = .waitingForUser
                    default:
                        self.status = .idle
                    }

                    if stateResponse.status != "waiting_for_user" {
                        self.isApprovalSubmitting = false
                    } else if newPromptId != self.pendingPromptId {
                        self.isApprovalSubmitting = false
                    }
                    self.pendingPromptId = newPromptId

                    // Speak user prompts and completion messages once. This uses
                    // ElevenLabs when configured, otherwise native macOS speech.
                    let shouldSpeak = stateResponse.status == "waiting_for_user" ||
                        stateResponse.status == "completed"
                    let voiceKey = "\(stateResponse.status):\(newNudge)"
                    if shouldSpeak,
                       !newNudge.isEmpty,
                       voiceKey != self.lastSpokenMessageKey {
                        self.speechManager.speak(newNudge)
                        self.lastSpokenMessageKey = voiceKey
                    } else if newNudge.isEmpty {
                        self.lastSpokenMessageKey = ""
                    }
                }
            } catch {
                // Keep polling silently
            }
        }.resume()
    }
    
    func sendInstruction() {
        guard !promptText.isEmpty else { return }
        
        let instruction = promptText
        let responsePromptId = status == .waitingForUser ? pendingPromptId : nil
        print("[Notch UI] User submitted instruction: \(instruction)")
        
        // Clear input bar
        promptText = ""
        speechManager.transcription = ""
        
        // Post instruction to our running Port 8420 Orchestrator
        self.status = .working
        
        guard let url = URL(string: "http://127.0.0.1:8420/instruction") else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        var body: [String: Any] = ["goal": instruction]
        if let responsePromptId = responsePromptId {
            body["prompt_id"] = responsePromptId
        }
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body, options: [])
        } catch {
            print("Failed to serialize goal: \(error)")
            return
        }
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                print("Instruction post error: \(error)")
            } else {
                print("Instruction successfully sent to Orchestrator.")
                // Immediate sync
                fetchOrchestratorState()
            }
        }.resume()
    }
}

// macOS Visual Effect View backing for premium glassmorphism HUD window
struct VisualEffectView: NSViewRepresentable {
    var material: NSVisualEffectView.Material
    var blendingMode: NSVisualEffectView.BlendingMode

    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.material = material
        view.blendingMode = blendingMode
        view.state = .active
        return view
    }

    func updateNSView(_ nsView: NSVisualEffectView, context: Context) {
        nsView.material = material
        nsView.blendingMode = blendingMode
    }
}

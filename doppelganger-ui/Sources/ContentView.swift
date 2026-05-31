import SwiftUI

enum AgentStatus {
    case idle
    case working
    case waitingForUser
    case completed   // brief celebratory state right after a task finishes
}

struct OrchestratorState: Codable {
    let status: String
    let nudge_message: String
    let logs: [String]
    let step_count: Int
    let pending_prompt_id: Int?
    let speech_seq: Int?
}

struct ContentView: View {
    @StateObject private var speechManager = SpeechManager.shared
    @StateObject private var supervisor = ProcessSupervisor.shared

    @State private var status: AgentStatus = .idle
    @State private var promptText: String = ""
    @State private var nudgeMessage: String = ""
    @State private var timer: Timer? = nil
    @State private var logs: [String] = []
    @State private var stepCount: Int = 0
    @State private var pendingPromptId: Int? = nil
    @State private var isApprovalSubmitting: Bool = false
    @State private var lastSpokenMessageKey: String = ""
    // Show the happy duck for a few seconds after a task completes, then go back to idle.
    @State private var completedShownAt: Date? = nil
    @State private var lastCompletionSeq: Int = -1

    // Floating-widget interaction state
    @State private var isHovering: Bool = false
    @State private var isPinned: Bool = false
    @State private var collapseWorkItem: DispatchWorkItem? = nil

    private let mascotSize: CGFloat = 84

    /// Stay expanded if any of: hovering, pinned, mid-input, recording, or a nudge is awaiting approval.
    private var shouldExpand: Bool {
        isHovering
            || isPinned
            || !promptText.isEmpty
            || speechManager.isRecording
            || status == .waitingForUser
    }

    var body: some View {
        // Anchor the widget to the top-right of the (transparent) window so
        // the mascot sits in the corner and the expanded panel grows down-left.
        VStack(alignment: .trailing, spacing: 8) {
            mascotPill

            if shouldExpand {
                expandedPanel
                    .transition(.asymmetric(
                        insertion: .opacity.combined(with: .move(edge: .top)),
                        removal: .opacity.combined(with: .move(edge: .top))
                    ))
            }
        }
        .padding(.horizontal, 20)
        .padding(.top, 4)
        .frame(width: 400, alignment: .trailing)
        .animation(.spring(response: 0.35, dampingFraction: 0.85), value: shouldExpand)
        .onAppear { startStatePolling() }
        .onDisappear { stopStatePolling() }
        .onReceive(speechManager.$transcription) { text in
            if speechManager.isRecording {
                self.promptText = text
            }
        }
    }

    // MARK: - Resting mascot pill

    private var mascotPill: some View {
        HStack(spacing: 10) {
            MascotView(status: status, size: 48)

            if shouldExpand {
                Text(pillLabel)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(.white.opacity(0.85))
                    .lineLimit(1)
                    .fixedSize()

                Button(action: { isPinned.toggle() }) {
                    Image(systemName: isPinned ? "pin.fill" : "pin")
                        .font(.system(size: 11))
                        .foregroundColor(isPinned ? .beakYellow : .white.opacity(0.45))
                        .rotationEffect(.degrees(isPinned ? 0 : 45))
                }
                .buttonStyle(PlainButtonStyle())
                .help(isPinned ? "Unpin panel" : "Pin panel open")

                Button(action: { NSApplication.shared.terminate(nil) }) {
                    Image(systemName: "xmark")
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundColor(.white.opacity(0.45))
                }
                .buttonStyle(PlainButtonStyle())
                .help("Quit Doppelgänger OS")
            }
        }
        .padding(.horizontal, shouldExpand ? 12 : 8)
        .padding(.vertical, 6)
        .frame(height: mascotSize - 24)
        .glassPanel(cornerRadius: (mascotSize - 24) / 2)
        .onHover { hovering in
            handleHover(hovering)
        }
        // Click the mascot to toggle the panel open/closed (like the old chevron),
        // alongside hover-to-peek. Pinning keeps it open when the mouse leaves.
        .onTapGesture {
            withAnimation(.spring(response: 0.35, dampingFraction: 0.85)) {
                isPinned.toggle()
            }
        }
        .help(isPinned ? "Click to collapse" : "Click to keep open")
    }

    // MARK: - Expanded panel

    private var expandedPanel: some View {
        VStack(spacing: 12) {
            PipView()
                .frame(height: 180)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))

            if !nudgeMessage.isEmpty {
                nudgeBlock
            }

            if !logs.isEmpty {
                consoleBlock
            }

            chatBar

            orchestratorControls
        }
        .padding(12)
        .frame(width: 360, alignment: .leading)
        .glassPanel(cornerRadius: 14)
        .onHover { hovering in
            handleHover(hovering)
        }
    }

    private var nudgeBlock: some View {
        HStack(alignment: .top, spacing: 10) {
            VStack(alignment: .leading, spacing: 3) {
                Text("Nudge")
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundColor(.beakYellow)
                    .textCase(.uppercase)
                    .tracking(0.6)
                Text(nudgeMessage)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundColor(.white.opacity(0.9))
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 0)

            if status == .waitingForUser {
                Button(action: {
                    guard !isApprovalSubmitting else { return }
                    self.promptText = "yes"
                    self.isApprovalSubmitting = true
                    self.nudgeMessage = ""
                    sendInstruction()
                }) {
                    Text(isApprovalSubmitting ? "Sent" : "Approve")
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundColor(.white)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(Color.mallardGreen.opacity(isApprovalSubmitting ? 0.4 : 0.9))
                        .clipShape(Capsule())
                }
                .disabled(isApprovalSubmitting)
                .buttonStyle(PlainButtonStyle())
            }
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(Color.beakYellow.opacity(0.25), lineWidth: 0.5)
        )
    }

    private var consoleBlock: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Console")
                .font(.system(size: 9, weight: .semibold))
                .foregroundColor(.white.opacity(0.4))
                .textCase(.uppercase)
                .tracking(0.6)

            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 3) {
                        ForEach(0..<logs.count, id: \.self) { idx in
                            Text(logs[idx])
                                .font(.system(size: 9, weight: .medium, design: .monospaced))
                                .foregroundColor(logColor(logs[idx]))
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .id(idx)
                        }
                    }
                }
                .frame(height: 90)
                .onAppear { proxy.scrollTo(logs.count - 1) }
                .onChange(of: logs) { _ in proxy.scrollTo(logs.count - 1) }
            }
            .padding(8)
            .background(Color.white.opacity(0.04))
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(Color.white.opacity(0.06), lineWidth: 0.5)
            )
        }
    }

    private var chatBar: some View {
        HStack(spacing: 8) {
            Button(action: {
                if speechManager.isRecording {
                    speechManager.stopRecording()
                    self.promptText = speechManager.transcription
                } else {
                    speechManager.beginRecordingWithPermissions()
                }
            }) {
                Image(systemName: speechManager.isRecording ? "mic.fill" : "mic")
                    .font(.system(size: 12))
                    .foregroundColor(speechManager.isRecording ? .beakYellow : .white.opacity(0.75))
                    .frame(width: 28, height: 28)
                    .background(speechManager.isRecording ? Color.beakYellowSoft : Color.white.opacity(0.05))
                    .clipShape(Circle())
            }
            .buttonStyle(PlainButtonStyle())

            TextField(
                speechManager.isRecording ? "Listening…" : "Tell the twin what to do…",
                text: $promptText,
                axis: .vertical
            )
            .lineLimit(1...5)
            .textFieldStyle(PlainTextFieldStyle())
            .font(.system(size: 11))
            .foregroundColor(.white)
            .tint(.mallardGreen)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .frame(minHeight: 28)
            .background(Color.white.opacity(0.05))
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(Color.white.opacity(0.08), lineWidth: 0.5)
            )
            .onSubmit { sendInstruction() }

            Button(action: sendInstruction) {
                Image(systemName: "arrow.up")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(.white)
                    .frame(width: 28, height: 28)
                    .background(promptText.isEmpty ? Color.mallardGreen.opacity(0.35) : Color.mallardGreen)
                    .clipShape(Circle())
            }
            .buttonStyle(PlainButtonStyle())
            .disabled(promptText.isEmpty)
        }
    }

    private var orchestratorControls: some View {
        HStack {
            HStack(spacing: 6) {
                Circle()
                    .fill(supervisor.isOrchestratorRunning ? Color.mallardGreen : Color.white.opacity(0.3))
                    .frame(width: 6, height: 6)
                Text(supervisor.isOrchestratorRunning ? "ORCHESTRATOR ACTIVE" : "ORCHESTRATOR OFFLINE")
                    .font(.system(size: 9, weight: .semibold, design: .monospaced))
                    .foregroundColor(.white.opacity(0.55))
                    .tracking(0.4)
            }

            Spacer()

            Button(action: {
                if supervisor.isOrchestratorRunning {
                    supervisor.stopOrchestrator()
                } else {
                    supervisor.startOrchestrator()
                }
            }) {
                Text(supervisor.isOrchestratorRunning ? "Stop" : "Start")
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundColor(.white.opacity(0.9))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 3)
                    .background(Color.white.opacity(0.08))
                    .clipShape(Capsule())
            }
            .buttonStyle(PlainButtonStyle())
        }
        .padding(.top, 2)
    }

    // MARK: - Hover handling

    private func handleHover(_ hovering: Bool) {
        collapseWorkItem?.cancel()
        if hovering {
            isHovering = true
        } else {
            // Small grace period so moving the cursor between mascot and panel
            // doesn't cause the panel to flicker shut.
            let item = DispatchWorkItem { self.isHovering = false }
            collapseWorkItem = item
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.25, execute: item)
        }
    }

    // MARK: - Labels & helpers

    var pillLabel: String {
        switch status {
        case .idle:           return "Ready"
        case .working:        return "Step \(stepCount)…"
        case .waitingForUser: return "Action needed"
        case .completed:      return "Done!"
        }
    }

    func logColor(_ text: String) -> Color {
        if text.contains("[!]") || text.contains("Error") || text.contains("failure") {
            return Color(red: 0.92, green: 0.45, blue: 0.45)
        } else if text.contains("[x]") || text.contains("Success") || text.contains("accomplished") {
            return .mallardGreen
        } else if text.contains("[Brain]") || text.contains("Thought") {
            return Color.white.opacity(0.7)
        } else if text.contains("[Step") {
            return .beakYellow
        } else {
            return Color.white.opacity(0.75)
        }
    }

    // MARK: - Networking (unchanged behavior)

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
            guard let data = data, error == nil else { return }
            do {
                let decoder = JSONDecoder()
                let stateResponse = try decoder.decode(OrchestratorState.self, from: data)
                DispatchQueue.main.async {
                    let newNudge = stateResponse.nudge_message
                    self.nudgeMessage = newNudge
                    self.logs = stateResponse.logs
                    self.stepCount = stateResponse.step_count
                    let newPromptId = stateResponse.pending_prompt_id

                    let seq = stateResponse.speech_seq ?? 0
                    switch stateResponse.status {
                    case "working":
                        self.status = .working
                    case "waiting_for_user":
                        self.status = .waitingForUser
                    case "completed":
                        // First time we see this completion, start the cheer timer.
                        if seq != self.lastCompletionSeq {
                            self.lastCompletionSeq = seq
                            self.completedShownAt = Date()
                        }
                        // Happy duck briefly, then settle back to sleeping (idle).
                        if let t = self.completedShownAt, Date().timeIntervalSince(t) < 4.0 {
                            self.status = .completed
                        } else {
                            self.status = .idle
                        }
                    default:
                        self.status = .idle
                    }

                    if stateResponse.status != "waiting_for_user" {
                        self.isApprovalSubmitting = false
                    } else if newPromptId != self.pendingPromptId {
                        self.isApprovalSubmitting = false
                    }
                    self.pendingPromptId = newPromptId

                    let shouldSpeak = stateResponse.status == "waiting_for_user" ||
                        stateResponse.status == "completed"
                    // Key on the server's speech sequence so each finished task / nudge
                    // speaks once — even when the text is identical to last time.
                    let voiceKey = "seq:\(stateResponse.speech_seq ?? 0)"
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

        promptText = ""
        speechManager.transcription = ""
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

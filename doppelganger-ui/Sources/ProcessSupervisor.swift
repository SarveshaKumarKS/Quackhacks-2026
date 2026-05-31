import Foundation

class ProcessSupervisor: ObservableObject {
    static let shared = ProcessSupervisor()
    
    @Published var isOrchestratorRunning = false
    @Published var orchestratorLogs = ""
    @Published var orchestratorExitCode: Int32? = nil
    
    private var process: Process?
    private var outputPipe: Pipe?
    
    private init() {}
    
    /// Launches the Python orchestrator script as a background subprocess
    func startOrchestrator(envPath: String? = nil, scriptPath: String = "../orchestrator/main.py") {
        guard process == nil else {
            print("[Supervisor] Orchestrator process is already active.")
            return
        }
        
        let newProcess = Process()
        let resolvedScriptPath = Bundle.main.bundlePath + "/" + scriptPath
        
        // Locate python: look for virtual env binary first, fallback to system
        let pythonExecutable = envPath ?? "/usr/bin/env"
        newProcess.executableURL = URL(fileURLWithPath: pythonExecutable)
        
        // Set arguments: if envPath isn't standard, we might invoke python directly
        if envPath == nil {
            newProcess.arguments = ["python3", scriptPath]
        } else {
            newProcess.arguments = [scriptPath]
        }
        
        // Configure standard input/output pipes
        let pipe = Pipe()
        newProcess.standardOutput = pipe
        newProcess.standardError = pipe
        self.outputPipe = pipe
        
        // Handle process termination events
        newProcess.terminationHandler = { [weak self] terminatedProc in
            DispatchQueue.main.async {
                self?.isOrchestratorRunning = false
                self?.orchestratorExitCode = terminatedProc.terminationStatus
                self?.process = nil
                print("[Supervisor] Orchestrator terminated with exit status \(terminatedProc.terminationStatus)")
            }
        }
        
        // Run asynchronously
        do {
            try newProcess.run()
            self.process = newProcess
            self.isOrchestratorRunning = true
            self.orchestratorExitCode = nil
            print("[Supervisor] Spawned orchestrator process on PID: \(newProcess.processIdentifier)")
            
            // Read output logs asynchronously
            readProcessOutput(pipe: pipe)
        } catch {
            self.isOrchestratorRunning = false
            print("[Supervisor] Failed to launch orchestrator: \(error)")
        }
    }
    
    /// Sends a SIGTERM signal to cleanly stop the Python orchestrator
    func stopOrchestrator() {
        guard let activeProcess = process else {
            return
        }
        
        print("[Supervisor] Stopping orchestrator process (PID: \(activeProcess.processIdentifier))...")
        // Send SIGTERM
        activeProcess.terminate()
        activeProcess.waitUntilExit()
        self.process = nil
        self.isOrchestratorRunning = false
    }
    
    private func readProcessOutput(pipe: Pipe) {
        let fileHandle = pipe.fileHandleForReading
        fileHandle.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if data.isEmpty { return }
            
            if let logString = String(data: data, encoding: .utf8) {
                DispatchQueue.main.async {
                    self?.orchestratorLogs.append(logString)
                    // Keep logs trimmed to prevent memory expansion
                    if (self?.orchestratorLogs.count ?? 0) > 10000 {
                        self?.orchestratorLogs = String((self?.orchestratorLogs.suffix(5000))!)
                    }
                }
            }
        }
    }
}

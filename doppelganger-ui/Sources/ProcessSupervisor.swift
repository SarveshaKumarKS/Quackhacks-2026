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
        
        // Resolve the absolute path of the orchestrator script robustly
        let fm = FileManager.default
        let currentDir = fm.currentDirectoryPath
        
        var resolvedScriptPath = scriptPath
        let pathOptions = [
            currentDir + "/orchestrator/main.py",
            currentDir + "/../orchestrator/main.py",
            Bundle.main.bundlePath + "/" + scriptPath,
            Bundle.main.bundlePath + "/../../../orchestrator/main.py",
            Bundle.main.bundlePath + "/../../../../orchestrator/main.py",
            Bundle.main.bundlePath + "/../../../../../orchestrator/main.py",
            scriptPath
        ]
        
        for option in pathOptions {
            if fm.fileExists(atPath: option) {
                resolvedScriptPath = option
                break
            }
        }
        print("[Supervisor] Resolved orchestrator script path to: \(resolvedScriptPath)")
        
        // Locate python: use user's Miniforge python to prevent ModuleNotFoundError
        let pythonExecutable = envPath ?? "/Users/sarveshaks/miniforge3/bin/python3"
        newProcess.executableURL = URL(fileURLWithPath: pythonExecutable)
        newProcess.arguments = [resolvedScriptPath]
        
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

# Doppelgänger OS — Manual Setup Runbook

Because Doppelgänger OS runs in a sandboxed sandbox environment on your real Mac across two user profiles, certain steps must be executed physically by the system administrator (you) to grant macOS permissions and set up credentials.

This runbook outlines every manual setup task and provides verification scripts to run to confirm success. Do not proceed with feature gates until the prerequisite manual steps below are confirmed.

---

## 1. Creating the Profile B macOS User Account
This creates the isolated desktop environment where the twin will execute browser actions, read Mail, and interact headlessly.

### Steps
1. Open **System Settings** -> **Users & Groups**.
2. Click **Add User...** (enter your administrator password).
3. Set **New Account** to **Standard**.
4. Set **Full Name** to `Clone` and **Account Name** (shortname) to `clone`.
5. Set a secure password and remember it.
6. Click **Create User**.

### Verification
Open Terminal on your main profile (Profile A) and confirm the user exists:
```bash
id clone
```
*Expected Output:* Active uid and gid listings for the `clone` user.

---

## 2. Granting Screen Recording + Accessibility Permissions (Profile B)
Profile B's session needs to capture screenshots (Quartz) and perform synthetic inputs (PyAutoGUI clicking/typing).

### Steps
1. Log in to the newly created **Clone** user profile (Fast User Switch to it).
2. Open terminal in **Clone** and run a mock mouse test script:
   ```python
   import pyautogui
   pyautogui.click(10, 10)
   ```
3. macOS will raise two permission modals:
   * **Screen Recording**: Prompting to allow terminal/agent-server to capture the screen. Click **Open System Settings** -> Toggle **ON**.
   * **Accessibility**: Prompting to allow synthetic control. Click **Open System Settings** -> Toggle **ON**.
4. Switch back to **Profile A** (your main session).

### Verification
We will verify this under **GATE 2** with a dedicated test script that triggers a click in the background session.

---

## 3. Granting Speech & Microphone Permissions (Profile A)
The native SwiftUI notch app running in Profile A needs permissions to capture your microphone and transcribe it using native macOS speech recognition.

### Steps
1. Open the SwiftUI notch application once built (or compile and launch it).
2. Click the **Microphone** icon or trigger a voice input command.
3. macOS will raise two distinct prompts:
   * **Microphone Access**: *"Doppelgänger UI would like to access the microphone."* -> Click **OK**.
   * **Speech Recognition Access**: *"Doppelgänger UI would like to access Speech Recognition."* -> Click **OK**.
4. If you miss them, navigate manually to **System Settings** -> **Privacy & Security** -> **Microphone** / **Speech Recognition** and verify `DoppelgangerOS` is toggled **ON**.

### Verification
Speak a simple word (e.g. *"Go"*) and confirm it populates the Notch UI text field.

---

## 4. BigQuery Service Account Key Setup
Durable persistent memory is backed by BigQuery in the Google Cloud Platform.

### Steps
1. Log in to the [Google Cloud Console](https://console.cloud.google.com).
2. Navigate to **IAM & Admin** -> **Service Accounts**.
3. Create a new service account with **BigQuery Admin** role permissions.
4. Click on the service account -> **Keys** tab -> **Add Key** -> **Create new key** (select **JSON** format).
5. Download the JSON key file.
6. Create a directory in your local workspace:
   ```bash
   mkdir -p orchestrator/keys
   ```
7. Move your downloaded key file to `orchestrator/keys/gcp-service-account.json`.
8. Ensure `.gitignore` ignores this folder.

### Verification
Run our idempotent self-bootstrapping script from Profile A to verify credentials and connection:
```bash
python3 orchestrator/setup_bigquery.py
```
*Expected Output:*
```
[*] Loading environment variables...
[*] Target GCP Project: your-project-id
[*] Using credentials at: keys/gcp-service-account.json
[*] Checking/Creating dataset: your-project-id.doppelganger_dataset...
[x] Dataset is ready.
[*] Checking/Creating table: your-project-id.doppelganger_dataset.agent_memory...
[x] Table is ready and matches required schema.
[x] BigQuery self-bootstrapping completed successfully.
```

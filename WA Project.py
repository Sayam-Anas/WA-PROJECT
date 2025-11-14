import customtkinter as ctk
from tkinter import filedialog
import webbrowser
import os
from typing import Optional, List
import pandas as pd
from pathlib import Path
import time
import pywhatkit as kit
import threading
from datetime import datetime

# Set appearance mode
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# --- Consistent Colors ---
DEFAULT_BLUE = "#007BFF"
DEFAULT_HOVER_BLUE = "#0056b3"
SEND_GREEN = "#388E3C"
SEND_HOVER_GREEN = "#2E7D32"
NAVIGATION_GRAY = "#9E9E9E"
NAVIGATION_HOVER_GRAY = "#757575"
LOGOUT_RED = "#E53935"


# ==========================================================
# FILE VALIDATION AND EXTRACTION UTILITIES
# ==========================================================
def load_and_validate_data(file_path: Path) -> pd.DataFrame:
    """Reads data into a pandas DataFrame, validating file type."""
    extension = file_path.suffix.lower()

    if extension == ".xlsx" or extension == ".xls":
        return pd.read_excel(file_path, engine='openpyxl')

    elif extension == ".csv":
        try:
            return pd.read_csv(file_path, encoding='utf-8')
        except UnicodeDecodeError:
            return pd.read_csv(file_path, encoding='latin-1')

    else:
        raise ValueError(f"Unsupported file type '{extension}'. Please use .xlsx, .xls, or .csv.")


def extract_and_format_phone_numbers(df: pd.DataFrame) -> List[str]:
    """
    Extracts phone number-like values from all cells in a DataFrame,
    cleans them, and formats them with the '+91' country code prefix.
    """
    if df.empty:
        return []

    all_values = df.values.flatten()
    unique_phone_numbers = set()

    for val in all_values:
        if pd.notna(val):
            s = str(val).strip().replace(" ", "").replace("-", "")
            if s.isdigit() or (s.startswith("+") and s[1:].isdigit()):
                unique_phone_numbers.add(s)

    formatted_numbers = []
    for number in unique_phone_numbers:
        if number.startswith("0") and len(number) > 1 and not number.startswith("+"):
            number = number[1:]

        if not number.startswith("+"):
            if len(number) == 10:
                number = "+91" + number

        formatted_numbers.append(number)

    return sorted([num for num in list(set(formatted_numbers)) if 11 <= len(num) <= 15])


# ==========================================================
# MESSAGE SENDING UTILITY (Threaded)
# ==========================================================
def send_whatsapp_messages_threaded(app_instance: ctk.CTk, formatted_numbers: List[str], message_content: str,
                                    start_index: int, stop_event: threading.Event) -> None:
    """
    Sends messages sequentially in a separate thread, respecting the stop_event.
    """
    total_numbers = len(formatted_numbers)

    if start_index > 0:
        app_instance.after(0, lambda: app_instance.write_to_log(f"Resuming from contact #{start_index + 1}.", "INFO"))

    for i in range(start_index, total_numbers):
        if stop_event.is_set():
            app_instance.after(0, lambda: app_instance._handle_send_paused(i))
            return

        number = formatted_numbers[i]

        app_instance.after(0, lambda n=number, idx=i: app_instance.write_to_log(
            f"Attempting to send message {idx + 1}/{total_numbers} to: {n}", "INFO"))

        try:
            kit.sendwhatmsg_instantly(
                number,
                message_content,
                wait_time=app_instance.wait_time_value,
                tab_close=True,
                close_time=3
            )
            timestamp = datetime.now().strftime("%H:%M:%S")
            status_text = f"[{timestamp}] ✅ {number}"
            app_instance.after(0, lambda t=status_text, n=number: app_instance._update_live_status(t, n, "Sent"))
            app_instance.after(0, lambda: setattr(app_instance, 'success_count', app_instance.success_count + 1))
            app_instance.current_index = i + 1
            app_instance.after(0, app_instance._check_send_button_state)
            time.sleep(1)

        except Exception as e:
            timestamp = datetime.now().strftime("%H:%M:%S")
            status_text = f"[{timestamp}] ❌ {number} - {str(e)[:30]}"
            app_instance.after(0, lambda t=status_text, n=number: app_instance._update_live_status(t, n, "Not Sent"))
            app_instance.after(0, lambda: setattr(app_instance, 'fail_count', app_instance.fail_count + 1))
            app_instance.current_index = i + 1
            app_instance.after(0, app_instance._check_send_button_state)
            time.sleep(2)

    app_instance.after(0, lambda: app_instance._handle_send_completed())


# ==========================================================
# DIALOG CLASSES
# ==========================================================
class HelpDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Help")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width, height = 520, 320
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

        self.parent = parent
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Title
        self.grid_rowconfigure(1, weight=1)  # Content
        self.grid_rowconfigure(2, weight=0)  # Timer button

        title_label = ctk.CTkLabel(
            self,
            text="💡 Help & Troubleshooting",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        title_label.grid(row=0, column=0, padx=20, pady=(25, 20), sticky="ew")

        # Content frame for bullet points
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.grid(row=1, column=0, padx=25, pady=10, sticky="nsew")
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_rowconfigure(1, weight=1)

        # First bullet point
        point1_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        point1_frame.grid(row=0, column=0, sticky="w", pady=(0, 15))
        point1_frame.grid_columnconfigure(0, weight=0)
        point1_frame.grid_columnconfigure(1, weight=1)

        bullet1 = ctk.CTkLabel(
            point1_frame,
            text="•",
            font=ctk.CTkFont(size=16, weight="bold"),
            width=20
        )
        bullet1.grid(row=0, column=0, sticky="nw", padx=(0, 10))

        message1_label = ctk.CTkLabel(
            point1_frame,
            text="If the message is not sent please increase the timer by one unit and try again...",
            font=ctk.CTkFont(size=14),
            wraplength=420,
            justify="left"
        )
        message1_label.grid(row=0, column=1, sticky="w")

        # Second bullet point
        point2_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        point2_frame.grid(row=1, column=0, sticky="w", pady=(0, 10))
        point2_frame.grid_columnconfigure(0, weight=0)
        point2_frame.grid_columnconfigure(1, weight=1)

        bullet2 = ctk.CTkLabel(
            point2_frame,
            text="•",
            font=ctk.CTkFont(size=16, weight="bold"),
            width=20
        )
        bullet2.grid(row=0, column=0, sticky="nw", padx=(0, 10))

        message2_label = ctk.CTkLabel(
            point2_frame,
            text="If the process is slow...! Please decrease the timer.",
            font=ctk.CTkFont(size=14),
            wraplength=420,
            justify="left"
        )
        message2_label.grid(row=0, column=1, sticky="w")

        # Timer button at the bottom
        timer_btn = ctk.CTkButton(
            self,
            text="Timer",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=40,
            fg_color=DEFAULT_BLUE,
            hover_color=DEFAULT_HOVER_BLUE,
            command=self.open_timer_settings
        )
        timer_btn.grid(row=2, column=0, padx=20, pady=(15, 25), sticky="ew")

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def open_timer_settings(self):
        """Open the wait time settings dialog"""
        self.destroy()
        self.parent.open_wait_time_settings()


class WaitTimeSettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, current_wait_time):
        super().__init__(parent)
        self.title("Timer Settings")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width, height = 520, 320
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

        self.result = None
        self.current_value = current_wait_time
        self.grid_columnconfigure(0, weight=1)

        # Configure row weights for proper spacing
        self.grid_rowconfigure(0, weight=0)  # Title
        self.grid_rowconfigure(1, weight=0)  # Info
        self.grid_rowconfigure(2, weight=1)  # Controls (expands)
        self.grid_rowconfigure(3, weight=0)  # Buttons

        title_label = ctk.CTkLabel(
            self,
            text="Adjust the Time for Sending the Message",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.grid(row=0, column=0, padx=20, pady=(25, 15), sticky="ew")

        info_label = ctk.CTkLabel(
            self,
            text="Set the wait time between sending messages",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        info_label.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")

        # Control frame with increment/decrement buttons
        control_frame = ctk.CTkFrame(self, fg_color="transparent")
        control_frame.grid(row=2, column=0, padx=20, pady=20, sticky="nsew")
        control_frame.grid_columnconfigure((0, 1, 2), weight=1)
        control_frame.grid_rowconfigure(0, weight=1)

        self.decrement_btn = ctk.CTkButton(
            control_frame,
            text="−",
            width=60,
            height=60,
            font=ctk.CTkFont(size=30, weight="bold"),
            fg_color=DEFAULT_BLUE,
            hover_color=DEFAULT_HOVER_BLUE,
            command=self.decrement_value
        )
        self.decrement_btn.grid(row=0, column=0, padx=5)

        self.value_label = ctk.CTkLabel(
            control_frame,
            text=f"{self.current_value}",
            font=ctk.CTkFont(size=36, weight="bold"),
            width=120
        )
        self.value_label.grid(row=0, column=1, padx=10)

        self.increment_btn = ctk.CTkButton(
            control_frame,
            text="+",
            width=60,
            height=60,
            font=ctk.CTkFont(size=30, weight="bold"),
            fg_color=DEFAULT_BLUE,
            hover_color=DEFAULT_HOVER_BLUE,
            command=self.increment_value
        )
        self.increment_btn.grid(row=0, column=2, padx=5)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, padx=20, pady=(15, 25), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            height=40,
            command=self.on_cancel
        )
        cancel_btn.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        save_btn = ctk.CTkButton(
            btn_frame,
            text="Save",
            height=40,
            fg_color=SEND_GREEN,
            hover_color=SEND_HOVER_GREEN,
            command=self.on_save
        )
        save_btn.grid(row=0, column=1, padx=(10, 0), sticky="ew")

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.update_button_states()

    def increment_value(self):
        if self.current_value < 100:
            self.current_value += 1
            self.value_label.configure(text=f"{self.current_value}")
            self.update_button_states()

    def decrement_value(self):
        if self.current_value > 7:
            self.current_value -= 1
            self.value_label.configure(text=f"{self.current_value}")
            self.update_button_states()

    def update_button_states(self):
        if self.current_value <= 7:
            self.decrement_btn.configure(state="disabled", fg_color="gray")
        else:
            self.decrement_btn.configure(state="normal", fg_color=DEFAULT_BLUE)

        if self.current_value >= 100:
            self.increment_btn.configure(state="disabled", fg_color="gray")
        else:
            self.increment_btn.configure(state="normal", fg_color=DEFAULT_BLUE)

    def on_save(self):
        self.result = self.current_value
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()


class ConfirmSendDialog(ctk.CTkToplevel):
    def __init__(self, parent, send_command):
        super().__init__(parent)
        self.title("Confirm Send")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width, height = 400, 140
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

        self.send_command = send_command
        self.grid_columnconfigure(0, weight=1)

        message_label = ctk.CTkLabel(self, text="Confirm to send Message !",
                                     font=ctk.CTkFont(size=16))
        message_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", command=self.on_cancel)
        cancel_btn.grid(row=0, column=0, padx=(0, 10))

        send_btn = ctk.CTkButton(btn_frame, text="SEND", fg_color="#388E3C", hover_color="#2E7D32",
                                 command=self.on_send)
        send_btn.grid(row=0, column=1, padx=(10, 0))

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def on_send(self):
        self.destroy()
        self.send_command()

    def on_cancel(self):
        self.destroy()


class ConfirmLogoutDialog(ctk.CTkToplevel):
    def __init__(self, parent, command):
        super().__init__(parent)
        self.title("Confirm Logout")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width, height = 350, 150
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

        self.command = command
        self.grid_columnconfigure(0, weight=1)

        message_label = ctk.CTkLabel(
            self,
            text="Are you sure you want to logout ?",
            font=ctk.CTkFont(size=16)
        )
        message_label.grid(row=0, column=0, padx=20, pady=20, sticky="ew")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self.on_cancel
        )
        cancel_btn.grid(row=0, column=0, padx=(0, 10))

        logout_btn = ctk.CTkButton(
            btn_frame,
            text="Logout",
            fg_color=LOGOUT_RED,
            hover_color="#C62828",
            command=self.on_logout
        )
        logout_btn.grid(row=0, column=1, padx=(10, 0))

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def on_logout(self):
        self.destroy()
        self.command()

    def on_cancel(self):
        self.destroy()


# ==========================================================
# MAIN APPLICATION CLASS
# ==========================================================
class CollegeApp(ctk.CTk):
    CORRECT_PASSWORD = "ASDFGHJK"

    VIEW_INITIAL = 0
    VIEW_UPLOAD = 1
    VIEW_MANUAL = 2

    MANUAL_ENTRY_PLACEHOLDER = "Enter Numbers (one per line)"
    PLACEHOLDER_COLOR = "gray60"

    ALLOWED_EXTENSIONS = ['.csv', '.xlsx', '.xls']

    def __init__(self):
        super().__init__()
        self.title("College App - Utility")
        self.after(1, self.wm_state, 'zoomed')
        self.after_id_status = None
        self.after_id_enable = None

        # Wait time configuration
        self.wait_time_value = 10

        # Status tracking for export
        self.status_records = []

        # UI Element References for Page 3
        self.status_textbox = None
        self.log_textbox = None
        self.numbers_textbox = None
        self.upload_buttons_frame = None
        self.back_button_upload = None
        self.message_textbox = None
        self.main_action_button = None
        self.initial_buttons_frame = None
        self.enter_numbers_button = None
        self.upload_numbers_button = None
        self.upload_view_elements = {}
        self.manual_entry_textbox = None
        self.download_button = None

        # State Variables for Page 3
        self.uploaded_file_path: Optional[str] = None
        self.contact_data: Optional[pd.DataFrame] = None
        self.formatted_numbers_list: List[str] = []
        self.toggle_upload_view_state = self.VIEW_INITIAL
        self.send_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.current_index = 0
        self.sending_state = "IDLE"
        self.success_count = 0
        self.fail_count = 0

        self.show_start_page()

    def open_wait_time_settings(self):
        """Open the wait time settings dialog"""
        dialog = WaitTimeSettingsDialog(self, self.wait_time_value)
        self.wait(window=dialog)
        if dialog.result is not None:
            self.wait_time_value = dialog.result
            if hasattr(self, 'log_textbox') and self.log_textbox:
                self.write_to_log(f"Wait time updated to {self.wait_time_value} seconds", "SUCCESS")

    def open_help_dialog(self):
        """Open the help dialog"""
        HelpDialog(self)

    def download_status_report(self):
        """Export status records to Excel file"""
        if not self.status_records:
            self.write_to_log("No status data to export.", "WARNING")
            return

        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                initialfile="status.xlsx"
            )

            if file_path:
                df = pd.DataFrame(self.status_records, columns=["Number", "Status"])
                df.to_excel(file_path, index=False, engine='openpyxl')
                self.write_to_log(f"Status report exported successfully to: {file_path}", "SUCCESS")
        except Exception as e:
            self.write_to_log(f"Failed to export status report: {e}", "ERROR")

    def show_download_button(self):
        """Show the download button in the status frame"""
        if self.download_button:
            self.download_button.grid()

    def hide_download_button(self):
        """Hide the download button"""
        if self.download_button:
            self.download_button.grid_remove()

    # ==========================================================
    # PAGE 1 & 2 METHODS
    # ==========================================================
    def show_delayed_status_message(self):
        """Updates the label 5 seconds after the browser opens with the single instruction."""
        self.whatsapp_error_label.configure(
            text="Please ensure that you have logged in to WhatsApp.",
            text_color="orange"
        )

    def enable_proceed_button(self):
        """Enables the Proceed button 10 seconds after the browser opens."""
        self.proceed_btn.configure(state="normal", fg_color="#25D366", hover_color="#1DA84E")

    def cancel_pending_timers(self):
        """Cancels any running self.after calls to prevent issues when resetting."""
        if self.after_id_status:
            try:
                self.after_cancel(self.after_id_status)
            except ValueError:
                pass
        if self.after_id_enable:
            try:
                self.after_cancel(self.after_id_enable)
            except ValueError:
                pass

    def open_whatsapp_browser(self):
        self.cancel_pending_timers()
        self.proceed_btn.configure(state="disabled", fg_color="gray", hover_color="gray")
        webbrowser.open("https://web.whatsapp.com/")
        self.whatsapp_error_label.configure(
            text="Opening WhatsApp Web...",
            text_color="blue"
        )
        self.after_id_status = self.after(5000, self.show_delayed_status_message)
        self.after_id_enable = self.after(10000, self.enable_proceed_button)

    def proceed_to_utility(self):
        self.cancel_pending_timers()
        # Direct transition to utility page
        for widget in self.winfo_children():
            widget.destroy()
        self.show_main_utility_page()

    def focus_password(self, event=None):
        """Move focus to password field when Enter is pressed in username field"""
        self.password_entry.focus()
        return "break"

    def login_attempt(self, event=None):
        entered_password = self.password_entry.get()
        if entered_password == self.CORRECT_PASSWORD:
            self.error_label.configure(text="")
            self.show_whatsapp_setup_page()
        else:
            self.error_label.configure(text="Access Denied!", text_color="red")
            self.password_entry.delete(0, 'end')

    def show_start_page(self):
        for widget in self.winfo_children():
            widget.destroy()

        frame = ctk.CTkFrame(self, corner_radius=20)
        frame.pack(expand=True, fill="both", padx=100, pady=100)

        COMFORTABLE_WIDTH = 320

        label = ctk.CTkLabel(
            frame,
            text="College App Login",
            font=ctk.CTkFont(size=26, weight="bold")
        )
        label.pack(pady=(80, 40))

        self.username_entry = ctk.CTkEntry(
            frame,
            placeholder_text="Username",
            width=COMFORTABLE_WIDTH,
            height=45,
            corner_radius=8,
            font=ctk.CTkFont(size=16)
        )
        self.username_entry.pack(pady=12)
        self.username_entry.bind('<Return>', self.focus_password)

        self.password_entry = ctk.CTkEntry(
            frame,
            placeholder_text="Password",
            width=COMFORTABLE_WIDTH,
            height=45,
            corner_radius=8,
            show="*",
            font=ctk.CTkFont(size=16)
        )
        self.password_entry.pack(pady=12)
        self.password_entry.bind('<Return>', self.login_attempt)

        start_button = ctk.CTkButton(
            frame,
            text="Log In",
            font=ctk.CTkFont(size=18, weight="bold"),
            width=COMFORTABLE_WIDTH,
            height=55,
            corner_radius=8,
            command=self.login_attempt
        )
        start_button.pack(pady=(35, 10))

        self.error_label = ctk.CTkLabel(
            frame,
            text="",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="red"
        )
        self.error_label.pack(pady=(5, 70))

    def show_whatsapp_setup_page(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.after_id_status = None
        self.after_id_enable = None

        content_frame = ctk.CTkFrame(self, corner_radius=20)
        content_frame.pack(expand=True, fill="both", padx=100, pady=100)

        back_btn = ctk.CTkButton(
            self,
            text="← Back to Login",
            width=150,
            height=40,
            command=self.show_start_page
        )
        back_btn.place(relx=0.05, rely=0.05, anchor=ctk.NW)

        title_label = ctk.CTkLabel(
            content_frame,
            text="WhatsApp Utility Setup",
            font=ctk.CTkFont(size=36, weight="bold")
        )
        title_label.pack(pady=(80, 40))

        info_label = ctk.CTkLabel(
            content_frame,
            text=("Click **'Open WhatsApp Web'** to launch the page.\n"
                  "Log in (scan QR code if needed) in your browser.\n"
                  "Wait 10 seconds, then click **'Proceed'** to continue."),
            font=ctk.CTkFont(size=18),
            justify="left"
        )
        info_label.pack(pady=20)

        self.open_browser_btn = ctk.CTkButton(
            content_frame,
            text="Open WhatsApp Web",
            font=ctk.CTkFont(size=20, weight="bold"),
            width=300,
            height=50,
            corner_radius=15,
            fg_color="#25D366",
            hover_color="#1DA84E",
            command=self.open_whatsapp_browser
        )
        self.open_browser_btn.pack(pady=(30, 10))

        self.proceed_btn = ctk.CTkButton(
            content_frame,
            text="Proceed",
            font=ctk.CTkFont(size=20, weight="bold"),
            width=300,
            height=50,
            corner_radius=15,
            fg_color="gray",
            hover_color="gray",
            state="disabled",
            command=self.proceed_to_utility
        )
        self.proceed_btn.pack(pady=(10, 30))

        self.whatsapp_error_label = ctk.CTkLabel(
            content_frame,
            text="",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="gray"
        )
        self.whatsapp_error_label.pack(pady=(10, 70))

    # ==========================================================
    # PAGE 3 METHODS
    # ==========================================================
    def _update_live_status(self, text, number, status):
        """Appends a new line to the Status box showing all sent messages and tracks status."""
        # Add to status records for export
        self.status_records.append([number, status])

        if self.status_textbox:
            self.status_textbox.configure(state="normal")
            current_content = self.status_textbox.get("1.0", "end-1c")
            if current_content.strip():
                self.status_textbox.insert("end", "\n" + text)
            else:
                self.status_textbox.insert("end", text)
            self.status_textbox.see("end")
            self.status_textbox.configure(state="disabled")

    def add_manual_placeholder(self, event=None):
        """Adds placeholder text if the box is empty."""
        if self.manual_entry_textbox and not self.manual_entry_textbox.get("1.0", "end-1c").strip():
            self.manual_entry_textbox.delete("1.0", "end")
            self.manual_entry_textbox.insert("1.0", self.MANUAL_ENTRY_PLACEHOLDER)
            self.manual_entry_textbox.configure(text_color=self.PLACEHOLDER_COLOR)
            self.manual_entry_textbox.bind("<Key>", self.remove_manual_placeholder_on_key)
            self.manual_entry_textbox.unbind("<FocusIn>")

    def remove_manual_placeholder(self, event=None):
        """Removes placeholder on FocusIn."""
        if self.is_manual_placeholder_active():
            self.manual_entry_textbox.delete("1.0", "end")
            self.manual_entry_textbox.configure(text_color=self.cget("text_color"))
            self.manual_entry_textbox.unbind("<Key>")

    def remove_manual_placeholder_on_key(self, event):
        """Removes placeholder on the first key press, before the character is inserted."""
        if self.is_manual_placeholder_active():
            if event.keysym not in ('Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Caps_Lock'):
                self.manual_entry_textbox.delete("1.0", "end")
                self.manual_entry_textbox.configure(text_color=self.cget("text_color"))
                self.manual_entry_textbox.unbind("<Key>")

    def is_manual_placeholder_active(self):
        return self.manual_entry_textbox and self.manual_entry_textbox.get("1.0",
                                                                           "end-1c").strip() == self.MANUAL_ENTRY_PLACEHOLDER

    def write_to_log(self, text, level="INFO"):
        """Writes text to the log textbox with color based on the level using tags."""
        if self.log_textbox:
            self.log_textbox.configure(state="normal")

            color_map = {
                "INFO": "blue",
                "SUCCESS": SEND_GREEN,
                "ERROR": LOGOUT_RED,
                "WARNING": "orange"
            }

            level = level.upper()
            color = color_map.get(level, "black")
            tag_name = f"{level.lower()}_tag"

            try:
                self.log_textbox.tag_config(tag_name, foreground=color)
            except Exception:
                pass

            self.log_textbox.insert("end", f"\n{text}", tag_name)
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")

    def _update_numbers_textbox(self):
        numbers_display = "\n".join(self.formatted_numbers_list)

        if self.numbers_textbox:
            self.numbers_textbox.configure(state="normal")
            self.numbers_textbox.delete("1.0", "end")
            self.numbers_textbox.insert("end", numbers_display)
            self.numbers_textbox.configure(state="disabled")

        self._check_send_button_state()

    def _check_send_button_state(self, event=None):
        """Controls the state, text, and color of the Send/Stop/Continue button."""
        if not self.message_textbox: return

        current_text = self.message_textbox.get("1.0", "end-1c").strip()
        message_is_ready = bool(current_text)
        numbers_are_ready = bool(self.formatted_numbers_list)

        if hasattr(self, 'main_action_button') and self.main_action_button:
            button = self.main_action_button

            if self.toggle_upload_view_state == self.VIEW_MANUAL:
                self._check_manual_process_button_state()
                return

            if self.toggle_upload_view_state == self.VIEW_UPLOAD:
                if not numbers_are_ready:
                    button.configure(state="normal")
                    return

            if self.sending_state == "SENDING":
                button.configure(state="normal", text="Stop", fg_color=LOGOUT_RED, hover_color="#C62828",
                                 text_color="white")

            elif self.sending_state == "PAUSED":
                remaining = len(self.formatted_numbers_list) - self.current_index
                button.configure(state="normal", text=f"Continue ({remaining} left)",
                                 fg_color="#FBC02D", hover_color="#F9A825", text_color="black")
                self.show_download_button()

            elif self.sending_state == "DONE":
                button.configure(state="disabled", text="Done ✅",
                                 fg_color=SEND_GREEN, hover_color=SEND_HOVER_GREEN, text_color="white")
                self.show_download_button()

            elif message_is_ready and numbers_are_ready and self.sending_state == "IDLE":
                button.configure(state="normal", text="Send Message",
                                 fg_color=SEND_GREEN, hover_color=SEND_HOVER_GREEN, text_color="white")

            else:
                button.configure(state="disabled", text="Send Message", fg_color="gray", text_color="white")

    def _handle_send_paused(self, stopped_index):
        """Called by the background thread when it pauses."""
        self.write_to_log(f"--- Sending PAUSED at contact #{stopped_index} ---", "WARNING")

        # Mark remaining numbers as "Not Attempted"
        for i in range(stopped_index, len(self.formatted_numbers_list)):
            number = self.formatted_numbers_list[i]
            self.status_records.append([number, "Not Attempted"])

        self.current_index = stopped_index
        self.sending_state = "PAUSED"
        self._check_send_button_state()

    def _handle_send_completed(self):
        """Called by the background thread when it finishes all messages."""
        self.write_to_log(f"--- Message Sending Complete ---", "INFO")
        self.write_to_log(f"Summary: {self.success_count} successful, {self.fail_count} failed.", "INFO")
        self.current_index = 0
        self.sending_state = "DONE"
        self.send_thread = None
        self._check_send_button_state()

    def start_sending(self):
        """Starts or Resumes the sending process in a new thread."""
        if not self.formatted_numbers_list or not self.message_textbox.get("1.0", "end-1c").strip():
            self.write_to_log("Cannot start: Missing message or numbers.", "ERROR")
            return

        if self.sending_state == "DONE":
            self.current_index = 0
            self.success_count = 0
            self.fail_count = 0
            self.status_records = []
            # Clear status box for new sending session
            if self.status_textbox:
                self.status_textbox.configure(state="normal")
                self.status_textbox.delete("1.0", "end")
                self.status_textbox.configure(state="disabled")
            self.hide_download_button()

        self.stop_event.clear()
        self.sending_state = "SENDING"

        start_idx = self.current_index
        message_content = self.message_textbox.get("1.0", "end-1c").strip()

        self.write_to_log(f"Starting or resuming send process...", "INFO")

        self.send_thread = threading.Thread(
            target=send_whatsapp_messages_threaded,
            args=(self, self.formatted_numbers_list, message_content, start_idx, self.stop_event),
            daemon=True
        )
        self.send_thread.start()
        self._check_send_button_state()

    def pause_sending(self):
        """Sets the stop_event flag for the thread to stop at the next opportunity."""
        if self.send_thread and self.send_thread.is_alive():
            self.stop_event.set()
            self.write_to_log("Pausing process... Waiting for current message send to complete.", "WARNING")

    def handle_send_or_control(self):
        """The main command for the Send/Stop/Continue button."""
        if self.sending_state == "IDLE" or self.sending_state == "DONE":
            if not self.formatted_numbers_list or not self.message_textbox.get("1.0", "end-1c").strip():
                self.write_to_log("Cannot start: Missing message or numbers.", "ERROR")
                return
            ConfirmSendDialog(self, send_command=self.start_sending)

        elif self.sending_state == "SENDING":
            self.pause_sending()

        elif self.sending_state == "PAUSED":
            self.start_sending()

    def on_drop_zone_click(self, event=None):
        """Handle click on drop zone to open file dialog"""
        self.upload_numbers_command()

    def upload_numbers_command(self):
        """Opens the file dialog."""
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("All supported files", "*.csv *.xlsx *.xls"),
                ("CSV files", "*.csv"),
                ("Excel files (XLSX)", "*.xlsx"),
                ("Excel files (XLS)", "*.xls"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self.validate_and_load_file(file_path)
        else:
            self.toggle_upload_view(self.VIEW_UPLOAD)

    def validate_and_load_file(self, file_path: str) -> bool:
        if not file_path: return False

        path_obj = Path(file_path)
        filename = path_obj.name

        self.contact_data = None
        self.uploaded_file_path = None
        self.formatted_numbers_list = []
        self.current_index = 0
        self.sending_state = "IDLE"
        self.success_count = 0
        self.fail_count = 0
        self.status_records = []

        try:
            df = load_and_validate_data(path_obj)
            self.formatted_numbers_list = extract_and_format_phone_numbers(df)

            self.uploaded_file_path = file_path
            self.contact_data = df

            drop_zone_text = f"Selected File:\n\n{filename}\n({len(self.formatted_numbers_list)} unique numbers ready)"
            text_color = SEND_GREEN if self.formatted_numbers_list else LOGOUT_RED

            self.upload_view_elements['drop_zone_label'].configure(text=drop_zone_text, text_color=text_color)
            self.write_to_log(f"Successfully loaded {len(self.formatted_numbers_list)} numbers.", level="SUCCESS")
            self._update_numbers_textbox()

            self.toggle_upload_view(self.VIEW_INITIAL)
            return True

        except Exception as e:
            self.write_to_log(f"File process failed: {e}", level="ERROR")
            self.upload_view_elements['drop_zone_label'].configure(text="Click to Browse Excel/CSV File",
                                                                   text_color="gray50")
            self._update_numbers_textbox()
            self.main_action_button.configure(text="Browse File")
            return False

    def process_entered_numbers(self):
        if not self.manual_entry_textbox: return

        raw_text = self.manual_entry_textbox.get("1.0", "end").strip()
        if self.is_manual_placeholder_active():
            raw_text = ""

        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        valid_numbers = []
        for number in lines:
            cleaned_number = number.strip().replace(" ", "").replace("-", "")
            if cleaned_number.isdigit() or (cleaned_number.startswith("+") and cleaned_number[1:].isdigit()):
                valid_numbers.append(cleaned_number)

        formatted_numbers = []
        for number in valid_numbers:
            if number.startswith("0") and len(number) > 1 and not number.startswith("+"): number = number[1:]

            if not number.startswith("+"):
                if len(number) == 10:
                    number = "+91" + number

            formatted_numbers.append(number)

        final_filtered_numbers = []
        for num in list(set(formatted_numbers)):
            if 11 <= len(num) <= 15:
                final_filtered_numbers.append(num)

        self.formatted_numbers_list = sorted(final_filtered_numbers)
        self.contact_data = pd.DataFrame({'Number': self.formatted_numbers_list})
        self.current_index = 0
        self.sending_state = "IDLE"
        self.success_count = 0
        self.fail_count = 0
        self.status_records = []

        self._update_numbers_textbox()
        self.write_to_log(f"Manual entry processed: {len(self.formatted_numbers_list)} unique numbers loaded.",
                          level="SUCCESS")

        self.toggle_upload_view(self.VIEW_INITIAL)

    def _check_manual_process_button_state(self, event=None):
        """Enables the 'Process Numbers' button if the manual entry box has content."""
        if self.toggle_upload_view_state != self.VIEW_MANUAL or not self.manual_entry_textbox:
            return

        current_text = self.manual_entry_textbox.get("1.0", "end-1c").strip()

        if self.is_manual_placeholder_active():
            current_text = ""

        cleaned_input = current_text.replace(" ", "").replace("-", "")

        is_ready = len(cleaned_input) >= 10

        if self.main_action_button:
            if is_ready:
                self.main_action_button.configure(state="normal",
                                                  fg_color=DEFAULT_BLUE,
                                                  hover_color=DEFAULT_HOVER_BLUE,
                                                  text_color="white")
            else:
                self.main_action_button.configure(state="disabled",
                                                  fg_color="gray",
                                                  hover_color="gray",
                                                  text_color="white")

    def _hide_all_upload_elements(self):
        """Hides all elements in the dynamic frame using grid_forget()."""
        if self.initial_buttons_frame:
            self.initial_buttons_frame.grid_forget()

        for widget in self.upload_view_elements.values():
            widget.grid_forget()

        if self.manual_entry_textbox:
            self.manual_entry_textbox.grid_forget()

    def toggle_upload_view(self, view_state: int):
        self._hide_all_upload_elements()
        self.toggle_upload_view_state = view_state

        if view_state in [self.VIEW_UPLOAD, self.VIEW_MANUAL]:
            if self.formatted_numbers_list:
                self.formatted_numbers_list = []
                self.contact_data = None
                self.uploaded_file_path = None
                self.current_index = 0
                self.sending_state = "IDLE"
                self.success_count = 0
                self.fail_count = 0
                self.status_records = []
                self._update_numbers_textbox()
                self.write_to_log("Number list cleared. Ready for new input.", "INFO")
                self.hide_download_button()

        if view_state == self.VIEW_INITIAL:
            if self.back_button_upload:
                self.back_button_upload.grid_remove()
            if self.initial_buttons_frame:
                self.initial_buttons_frame.grid(row=1, column=0, sticky="nsew")

            self.main_action_button.configure(
                text="Send Message",
                command=self.handle_send_or_control,
                fg_color=SEND_GREEN, hover_color=SEND_HOVER_GREEN
            )

        else:
            if self.back_button_upload:
                self.back_button_upload.configure(fg_color=NAVIGATION_GRAY, hover_color=NAVIGATION_HOVER_GRAY)
                self.back_button_upload.grid(row=0, column=0, padx=10, pady=5, sticky="w")

            if view_state == self.VIEW_UPLOAD:
                drop_zone_text = "Click to Browse Excel/CSV File"
                text_color = "gray50"

                self.upload_view_elements['drop_zone_label'].configure(text=drop_zone_text, text_color=text_color)

                self.upload_buttons_frame.rowconfigure(1, weight=1)
                self.upload_buttons_frame.rowconfigure(2, weight=0)
                self.upload_view_elements['drop_zone_label'].grid(row=1, column=0, pady=(5, 10), padx=20, sticky="nsew")

                self.main_action_button.configure(
                    text="Browse File",
                    command=self.upload_numbers_command,
                    fg_color=DEFAULT_BLUE, hover_color=DEFAULT_HOVER_BLUE,
                    state="normal"
                )

            elif view_state == self.VIEW_MANUAL:
                self.upload_buttons_frame.rowconfigure(1, weight=1)
                self.upload_buttons_frame.rowconfigure(2, weight=0)

                self.manual_entry_textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=(10, 10))

                self.manual_entry_textbox.delete("1.0", "end")
                self.add_manual_placeholder()
                self.manual_entry_textbox.bind("<FocusIn>", self.remove_manual_placeholder)

                self.main_action_button.configure(
                    text="Process Numbers",
                    command=self.process_entered_numbers,
                    fg_color=DEFAULT_BLUE, hover_color=DEFAULT_HOVER_BLUE,
                    state="disabled"
                )
                self._check_manual_process_button_state()

        self._check_send_button_state()

    def show_main_utility_page(self):
        """Build page 3 with direct rendering"""
        # Pre-configure grid before adding widgets
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create main content frame
        content_frame = ctk.CTkFrame(self, corner_radius=20)
        content_frame.grid(row=0, column=0, sticky="nsew", padx=100, pady=100)
        content_frame.grid_columnconfigure(0, weight=2, uniform="main_col")
        content_frame.grid_columnconfigure(1, weight=1, uniform="main_col")
        content_frame.grid_rowconfigure(0, weight=1)

        def open_logout_dialog():
            ConfirmLogoutDialog(self, command=lambda: self.show_start_page())

        # Logout button (left side)
        logout_btn = ctk.CTkButton(
            self, text="Logout", width=150, height=40,
            fg_color=LOGOUT_RED, hover_color="#C62828", command=open_logout_dialog
        )
        logout_btn.place(relx=0.05, rely=0.05, anchor=ctk.NW)

        # Help button (right side) - same size as logout button
        help_btn = ctk.CTkButton(
            self, text="Help", width=150, height=40,
            fg_color=DEFAULT_BLUE, hover_color=DEFAULT_HOVER_BLUE,
            command=self.open_help_dialog
        )
        help_btn.place(relx=0.95, rely=0.05, anchor=ctk.NE)

        utility_panel = ctk.CTkFrame(content_frame, fg_color="transparent")
        utility_panel.grid(row=0, column=0, sticky="nsew", padx=(20, 10), pady=(20, 20))
        utility_panel.grid_columnconfigure(0, weight=1)
        utility_panel.grid_rowconfigure(0, weight=3)
        utility_panel.grid_rowconfigure(1, weight=2)
        utility_panel.grid_rowconfigure(2, weight=0)

        message_frame = ctk.CTkFrame(utility_panel, corner_radius=10, fg_color=self.cget("fg_color"))
        message_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        message_frame.grid_rowconfigure(1, weight=1)
        message_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(message_frame, text="Message", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0,
                                                                                                   pady=5, padx=10,
                                                                                                   sticky="w")
        self.message_textbox = ctk.CTkTextbox(message_frame, wrap="word", font=ctk.CTkFont(size=14))
        self.message_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.message_textbox.bind("<FocusOut>", self._check_send_button_state)
        self.message_textbox.bind("<KeyRelease>", self._check_send_button_state)

        mid_section_frame = ctk.CTkFrame(utility_panel, fg_color="transparent")
        mid_section_frame.grid(row=1, column=0, sticky="nsew", pady=10)
        mid_section_frame.grid_columnconfigure((0, 1), weight=1, uniform="mid_util_group")
        mid_section_frame.grid_rowconfigure(0, weight=1)

        upload_frame = ctk.CTkFrame(mid_section_frame, corner_radius=10, fg_color=self.cget("fg_color"))
        upload_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        upload_frame.columnconfigure(0, weight=1)
        upload_frame.rowconfigure(1, weight=1)

        title_frame = ctk.CTkFrame(upload_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", pady=(5, 0))
        title_frame.grid_columnconfigure(0, weight=1)
        title_frame.grid_columnconfigure(1, weight=0)
        title_frame.grid_columnconfigure(2, weight=1)

        self.back_button_upload = ctk.CTkButton(
            title_frame, text="Back", width=80, height=25, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=NAVIGATION_GRAY, hover_color=NAVIGATION_HOVER_GRAY,
            command=lambda: self.toggle_upload_view(self.VIEW_INITIAL)
        )
        self.back_button_upload.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        ctk.CTkLabel(title_frame, text="Upload", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=1, pady=5,
                                                                                                sticky="n")

        self.upload_buttons_frame = ctk.CTkFrame(upload_frame, fg_color="transparent")
        self.upload_buttons_frame.grid(row=1, column=0, sticky="nsew")
        self.upload_buttons_frame.columnconfigure(0, weight=1)
        self.upload_buttons_frame.rowconfigure(0, weight=0)
        self.upload_buttons_frame.rowconfigure(1, weight=1)
        self.upload_buttons_frame.rowconfigure(2, weight=0)

        self.initial_buttons_frame = ctk.CTkFrame(self.upload_buttons_frame, fg_color="transparent")
        self.initial_buttons_frame.columnconfigure(0, weight=1)

        self.enter_numbers_button = ctk.CTkButton(self.initial_buttons_frame, text="Enter Numbers", height=40,
                                                  font=ctk.CTkFont(size=16),
                                                  command=lambda: self.toggle_upload_view(self.VIEW_MANUAL),
                                                  fg_color=DEFAULT_BLUE, hover_color=DEFAULT_HOVER_BLUE
                                                  )
        self.enter_numbers_button.grid(row=0, column=0, pady=(20, 10), padx=20, sticky="ew")

        self.upload_numbers_button = ctk.CTkButton(self.initial_buttons_frame, text="Upload Numbers", height=40,
                                                   font=ctk.CTkFont(size=16),
                                                   command=lambda: self.toggle_upload_view(self.VIEW_UPLOAD),
                                                   fg_color=DEFAULT_BLUE, hover_color=DEFAULT_HOVER_BLUE
                                                   )
        self.upload_numbers_button.grid(row=1, column=0, pady=(40, 10), padx=20, sticky="ew")

        # Create clickable drop zone label
        self.upload_view_elements['drop_zone_label'] = ctk.CTkLabel(
            self.upload_buttons_frame,
            text="Click to Browse Excel/CSV File",
            text_color="gray50", fg_color="gray85", bg_color="transparent", corner_radius=10,
            font=ctk.CTkFont(size=14, weight="bold"), height=100, cursor="hand2"
        )
        # Bind click event to drop zone
        self.upload_view_elements['drop_zone_label'].bind("<Button-1>", self.on_drop_zone_click)

        self.manual_entry_textbox = ctk.CTkTextbox(self.upload_buttons_frame, wrap="word", font=ctk.CTkFont(size=14))
        self.manual_entry_textbox.bind("<KeyRelease>", self._check_manual_process_button_state)

        numbers_frame = ctk.CTkFrame(mid_section_frame, corner_radius=10, fg_color=self.cget("fg_color"))
        numbers_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        numbers_frame.grid_rowconfigure(1, weight=1)
        numbers_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(numbers_frame, text="Numbers List", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0,
                                                                                                        pady=5, padx=10,
                                                                                                        sticky="w")

        self.numbers_textbox = ctk.CTkTextbox(numbers_frame, wrap="word", font=ctk.CTkFont(size=14))
        self.numbers_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.numbers_textbox.configure(state="disabled")

        send_frame = ctk.CTkFrame(utility_panel, fg_color="transparent")
        send_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        send_frame.grid_columnconfigure(0, weight=1)

        self.main_action_button = ctk.CTkButton(
            send_frame, text="Send Message", font=ctk.CTkFont(size=20, weight="bold"),
            height=60, corner_radius=15,
            command=self.handle_send_or_control,
            fg_color=SEND_GREEN, hover_color=SEND_HOVER_GREEN
        )
        self.main_action_button.grid(row=0, column=0, padx=10, pady=0, sticky="ew")

        status_log_frame = ctk.CTkFrame(content_frame, corner_radius=10, fg_color=self.cget("fg_color"))
        status_log_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=(20, 20))
        status_log_frame.grid_columnconfigure(0, weight=1)
        status_log_frame.grid_rowconfigure(1, weight=1)
        status_log_frame.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(status_log_frame, text="Log", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0,
                                                                                                  pady=5, padx=10,
                                                                                                  sticky="w")
        self.log_textbox = ctk.CTkTextbox(status_log_frame, wrap="word", font=ctk.CTkFont(size=12))
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 5))
        self.log_textbox.configure(state="disabled")

        # Status section with title and download button
        status_header_frame = ctk.CTkFrame(status_log_frame, fg_color="transparent")
        status_header_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 0))
        status_header_frame.grid_columnconfigure(0, weight=1)
        status_header_frame.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(status_header_frame, text="Status", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w"
        )

        self.download_button = ctk.CTkButton(
            status_header_frame,
            text="📥 Download",
            width=100,
            height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=DEFAULT_BLUE,
            hover_color=DEFAULT_HOVER_BLUE,
            command=self.download_status_report
        )
        self.download_button.grid(row=0, column=1, sticky="e")
        self.download_button.grid_remove()  # Hide initially

        self.status_textbox = ctk.CTkTextbox(status_log_frame, wrap="word", font=ctk.CTkFont(size=12))
        self.status_textbox.grid(row=3, column=0, sticky="nsew", padx=10, pady=(5, 10))
        self.status_textbox.configure(state="disabled")

        self._update_live_status("", "", "")

        # Initialize view
        self.toggle_upload_view(self.VIEW_INITIAL)
        self._check_send_button_state()


if __name__ == "__main__":
    app = CollegeApp()
    app.mainloop()
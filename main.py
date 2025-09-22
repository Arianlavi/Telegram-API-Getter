import sys
import logging
import re
import requests
import time
import random
import string
from dataclasses import dataclass
from typing import Optional, Dict, List
from enum import Enum

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox, QTextEdit,
    QHBoxLayout, QProgressBar, QFrame, QGridLayout, QComboBox,
    QInputDialog
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
import pyperclip
from bs4 import BeautifulSoup

logging.basicConfig(
    filename='app_log.txt',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class TelegramAppRoutes:
    AUTH = '/auth/login'
    APPS = '/apps'
    CREATE_APP = '/apps/create'
    SEND_PASSWORD = '/auth/send_password'

class TelegramAppPlatformTypes(Enum):
    ANDROID = 'android'
    IOS = 'ios'
    WINDOWS_PHONE = 'wp'
    BLACKBERRY = 'bb'
    DESKTOP = 'desktop'
    WEB = 'web'
    UBUNTU_PHONE = 'ubp'
    OTHER = 'other'

@dataclass
class TelegramApp:
    app_title: str
    app_shortname: str
    app_platform: TelegramAppPlatformTypes
    app_url: Optional[str] = ''
    app_dsc: Optional[str] = ''

@dataclass
class TelegramAppCredentials:
    apiId: str
    apiHash: str

@dataclass
class TelegramAppAuthParams:
    phone: str
    random_hash: str
    code: str

class TelegramAppClient:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = 'https://my.telegram.org'
        self.cookie_name = 'stel_token'
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def log(self, text: str):
        logging.info(text)
        print(text)

    def normalize_phone_number(self, phone_number: str) -> str:
        phone = phone_number.strip().replace('+', '').replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
        if not phone.isdigit():
            raise ValueError('Invalid phone number')
        return phone

    def extract_csrf_token(self, html_content: str) -> Optional[str]:
        try:
            patterns = [
                r'name="csrf_token" value="([^"]+)"',
                r'csrf_token["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                r'<meta[^>]*name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html_content)
                if match:
                    return match.group(1)
            
            return None
            
        except Exception as e:
            self.log(f"Error extracting CSRF token: {e}")
            return None

    def send_confirmation_code(self, phone_number: str) -> Optional[str]:
        try:
            phone = self.normalize_phone_number(phone_number)
            
            response = self.session.get(f'{self.base_url}{TelegramAppRoutes.AUTH}', timeout=30)
            csrf_token = self.extract_csrf_token(response.text) or "default_csrf_token"
            
            data = {'phone': phone, 'csrf_token': csrf_token}
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': f'{self.base_url}{TelegramAppRoutes.AUTH}',
                'Origin': self.base_url
            }
            
            response = self.session.post(
                f'{self.base_url}{TelegramAppRoutes.SEND_PASSWORD}',
                data=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    if 'random_hash' in response_data:
                        return response_data['random_hash']
                except ValueError:
                    if 'random_hash' in response.text:
                        match = re.search(r'"random_hash":"([^"]+)"', response.text)
                        if match:
                            return match.group(1)
            
            return None
                
        except Exception as e:
            self.log(f"Error sending confirmation code: {str(e)}")
            return None

    def sign_in(self, params: TelegramAppAuthParams) -> Optional[str]:
        try:
            phone = self.normalize_phone_number(params.phone)
            
            response = self.session.get(f'{self.base_url}{TelegramAppRoutes.AUTH}', timeout=30)
            csrf_token = self.extract_csrf_token(response.text) or "default_csrf_token"
            
            data = {
                'phone': phone,
                'random_hash': params.random_hash,
                'password': params.code,
                'csrf_token': csrf_token
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Referer': f'{self.base_url}{TelegramAppRoutes.AUTH}',
                'Origin': self.base_url
            }
            
            response = self.session.post(
                f'{self.base_url}{TelegramAppRoutes.AUTH}',
                data=data,
                headers=headers,
                timeout=30,
                allow_redirects=True
            )
            
            stel_token = None
            if hasattr(response, 'cookies') and response.cookies:
                stel_token = response.cookies.get(self.cookie_name)
            
            if not stel_token:
                set_cookie = response.headers.get('Set-Cookie', '')
                if 'stel_token=' in set_cookie:
                    match = re.search(r'stel_token=([^;]+)', set_cookie)
                    if match:
                        stel_token = match.group(1)
            
            return stel_token
                
        except Exception as e:
            self.log(f"Error signing in: {str(e)}")
            return None

    def create_app_js_method(self, token: str, app_params: TelegramApp) -> bool:
        """Alternative method using JavaScript-like approach"""
        try:

            response = self.session.get(
                f'{self.base_url}{TelegramAppRoutes.APPS}',
                cookies={self.cookie_name: token},
                timeout=30
            )
            
            if response.status_code != 200:
                return False
            
            random_text_selection = list('abcdefghijklmnopqrstuvwxyz0123456789')
            random_title = ''.join(random.choices(random_text_selection, k=20))
            random_shortname = ''.join(random.choices(random_text_selection, k=20))
            
            self.log(f"Generated random title: {random_title}")
            self.log(f"Generated random shortname: {random_shortname}")
            

            soup = BeautifulSoup(response.text, 'html.parser')
            hash_input = soup.find('input', {'name': 'hash'})
            
            if not hash_input:
                match = re.search(r'name="hash" value="([^"]+)"', response.text)
                if match:
                    hash_value = match.group(1)
                else:
                    return False
            else:
                hash_value = hash_input.get('value', '')
            

            time.sleep(2)
            

            data = {
                'hash': hash_value,
                'app_title': random_title,
                'app_shortname': random_shortname,
                'app_url': 'https://example.com',
                'app_platform': 'other',
                'app_desc': 'Mobile application'
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Referer': f'{self.base_url}{TelegramAppRoutes.APPS}',
                'Origin': self.base_url
            }
            
            response = self.session.post(
                f'{self.base_url}{TelegramAppRoutes.CREATE_APP}',
                data=data,
                cookies={self.cookie_name: token},
                headers=headers,
                timeout=30
            )
            

            return True
                
        except Exception as e:
            self.log(f"Error in JS method app creation: {str(e)}")
            return True

    def get_credentials_advanced(self, token: str) -> Optional[TelegramAppCredentials]:
        """Advanced method to extract credentials with multiple techniques"""
        try:
            response = self.session.get(
                f'{self.base_url}{TelegramAppRoutes.APPS}',
                cookies={self.cookie_name: token},
                timeout=30
            )
            
            if response.status_code != 200:
                return None
            
            content = response.text
            self.log(f"Page content length: {len(content)}")
            

            soup = BeautifulSoup(content, 'html.parser')
            

            patterns = [
                # API ID patterns
                (r'api_id["\']?[^>]*>([^<]+)<', 'apiId'),
                (r'API ID[^>]*>([^<]+)<', 'apiId'),
                (r'<span[^>]*id=["\']app_id["\'][^>]*>([^<]+)</span>', 'apiId'),
                (r'<label[^>]*for=["\']app_id["\'][^>]*>[^<]*</label>[^<]*<span[^>]*>([^<]+)</span>', 'apiId'),
                
                # API Hash patterns
                (r'api_hash["\']?[^>]*>([^<]+)<', 'apiHash'),
                (r'API Hash[^>]*>([^<]+)<', 'apiHash'),
                (r'<span[^>]*id=["\']app_hash["\'][^>]*>([^<]+)</span>', 'apiHash'),
                (r'<label[^>]*for=["\']app_hash["\'][^>]*>[^<]*</label>[^<]*<span[^>]*>([^<]+)</span>', 'apiHash'),
            ]
            
            result = {'apiId': '', 'apiHash': ''}
            
            for pattern, key in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if match.strip():
                        result[key] = match.strip()
                        self.log(f"Found {key}: {result[key]}")
                        break
                if result['apiId'] and result['apiHash']:
                    break
            

            if not result['apiId'] or not result['apiHash']:
                form_groups = soup.find_all('div', class_='form-group')
                for group in form_groups:
                    label = group.find('label')
                    if label:
                        label_text = label.get_text().lower()
                        if 'api id' in label_text or 'app_id' in label_text:
                            span = group.find('span', class_='form-control')
                            if span:
                                result['apiId'] = span.get_text(strip=True)
                        elif 'api hash' in label_text or 'app_hash' in label_text:
                            span = group.find('span', class_='form-control')
                            if span:
                                result['apiHash'] = span.get_text(strip=True)
            

            if not result['apiId'] or not result['apiHash']:
                # Look for numeric API ID (usually 7-8 digits)
                api_id_match = re.search(r'\b(\d{7,8})\b', content)
                if api_id_match:
                    result['apiId'] = api_id_match.group(1)
                
                # Look for API Hash (32 character hex)
                api_hash_match = re.search(r'\b([a-f0-9]{32})\b', content)
                if api_hash_match:
                    result['apiHash'] = api_hash_match.group(1)
            
            if 'api_id' not in content.lower() and 'app_id' not in content.lower():
                self.log("API credentials section not found, might need to create app first")
                return None
            
            if result['apiId'] and result['apiHash']:
                return TelegramAppCredentials(
                    apiId=result['apiId'],
                    apiHash=result['apiHash']
                )
            
            self.log("Trying manual inspection of page content...")
            
            with open('debug_page.html', 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.log("Page content saved to debug_page.html for manual inspection")
            
            return None
                
        except Exception as e:
            self.log(f"Error getting credentials: {str(e)}")
            return None


class WorkerThread(QThread):
    update_result = pyqtSignal(str)
    append_log = pyqtSignal(str)
    show_message = pyqtSignal(str, str)
    set_running = pyqtSignal(bool)
    set_progress = pyqtSignal(int, int)
    request_code_input = pyqtSignal(str)

    def __init__(self, phone, app_title, app_shortname, app_url, app_platform='other'):
        super().__init__()
        self.phone = phone
        self.app_title = app_title
        self.app_shortname = app_shortname
        self.app_url = app_url
        self.app_platform = TelegramAppPlatformTypes(app_platform)
        self.client = TelegramAppClient()
        self.verification_code = None

    def log(self, text):
        logging.info(text)
        self.append_log.emit(text)

    def set_verification_code(self, code):
        self.verification_code = code

    def run(self):
        self.set_running.emit(True)
        self.set_progress.emit(0, 0)
        
        try:

            self.log("Sending confirmation code...")
            random_hash = self.client.send_confirmation_code(self.phone)
            
            if not random_hash:
                raise Exception("Failed to send confirmation code")
            
            self.log(f"Confirmation code sent. Random hash: {random_hash}")
            

            self.request_code_input.emit(self.phone)
            
            self.log("Waiting for verification code...")
            timeout = 300
            start_time = time.time()
            
            while self.verification_code is None and time.time() - start_time < timeout:
                time.sleep(0.5)
            
            if self.verification_code is None:
                raise Exception("Verification code timeout")
            
            self.log(f"Received verification code: {self.verification_code}")
            
            self.log("Signing in with verification code...")
            auth_params = TelegramAppAuthParams(
                phone=self.phone,
                random_hash=random_hash,
                code=self.verification_code
            )
            
            token = self.client.sign_in(auth_params)
            
            if not token:
                raise Exception("Failed to sign in")
            
            self.log(f"Signed in successfully. Token: {token}")
            
            self.log("Creating Telegram application with alternative method...")
            app_params = TelegramApp(
                app_title=self.app_title,
                app_shortname=self.app_shortname,
                app_url=self.app_url,
                app_platform=self.app_platform,
                app_dsc='Created via API'
            )
            
            success = self.client.create_app_js_method(token, app_params)
            
            if not success:
                self.log("App creation may have failed, but continuing...")
            
            self.log("Retrieving API credentials with advanced method...")
            
            credentials = None
            for attempt in range(5):  
                self.log(f"Attempt {attempt + 1} to get credentials...")
                credentials = self.client.get_credentials_advanced(token)
                if credentials:
                    break
                
                time.sleep(3)
                
                if attempt % 2 == 0:
                    self.log("Refreshing page...")
                    time.sleep(2)
            
            if not credentials:

                self.log("Final attempt: checking if app was created...")
                response = self.client.session.get(
                    f'{self.client.base_url}{TelegramAppRoutes.APPS}',
                    cookies={self.client.cookie_name: token},
                    timeout=30
                )
                
                if response.status_code == 200:

                    if 'application' in response.text.lower() or 'created' in response.text.lower():
                        self.log("App seems to be created but credentials not found")
                        credentials = self.extract_credentials_manual(response.text)
            
            if not credentials:
                raise Exception("Failed to retrieve API credentials. The app may have been created but credentials are not accessible.")
            
            result = f"✅ Success!\nAPI ID: {credentials.apiId}\nAPI Hash: {credentials.apiHash}"
            self.update_result.emit(result)
            self.log("API credentials retrieved successfully")
            self.show_message.emit("Success", result)
                
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.log(error_msg)
            self.show_message.emit("Error", error_msg)
        finally:
            self.set_progress.emit(0, 1)
            self.set_running.emit(False)
            self.log("Process completed")

    def extract_credentials_manual(self, html_content: str) -> Optional[TelegramAppCredentials]:
        """Manual extraction as last resort"""
        try:
            numbers = re.findall(r'\b(\d{7,9})\b', html_content)
            for num in numbers:
                if len(num) >= 7:  # API ID is usually 7-8 digits
                    hash_match = re.search(r'([a-f0-9]{32})', html_content[html_content.find(num):html_content.find(num)+200])
                    if hash_match:
                        return TelegramAppCredentials(apiId=num, apiHash=hash_match.group(1))
            
            return None
        except Exception as e:
            self.log(f"Error in manual extraction: {e}")
            return None


class TelegramAPIGetter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telegram API Getter - Ultimate Version")
        self.setFixedSize(700, 800)
        self.init_ui()
        self.worker = None
        self.current_credentials = ""

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        header = QLabel("🔐 Telegram API Getter - Ultimate Version")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #2D8CFF;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #f8f9fa;
                border-radius: 12px;
                border: 1px solid #e1e4e8;
                padding: 15px;
            }
        """)
        card_layout = QVBoxLayout(card)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("+989123456789")
        grid.addWidget(QLabel("📱 Phone Number:"), 0, 0)
        grid.addWidget(self.phone_input, 0, 1)

        self.app_title_input = QLineEdit()
        self.app_title_input.setPlaceholderText("My Telegram App")
        grid.addWidget(QLabel("📝 App Title:"), 1, 0)
        grid.addWidget(self.app_title_input, 1, 1)

        self.app_shortname_input = QLineEdit()
        self.app_shortname_input.setPlaceholderText("myapp")
        grid.addWidget(QLabel("🔤 Short Name:"), 2, 0)
        grid.addWidget(self.app_shortname_input, 2, 1)

        self.app_url_input = QLineEdit("https://example.com")
        grid.addWidget(QLabel("🌐 App URL:"), 3, 0)
        grid.addWidget(self.app_url_input, 3, 1)

        self.app_platform_input = QComboBox()
        self.app_platform_input.addItems([e.value for e in TelegramAppPlatformTypes])
        self.app_platform_input.setCurrentText(TelegramAppPlatformTypes.OTHER.value)
        grid.addWidget(QLabel("📱 Platform:"), 4, 0)
        grid.addWidget(self.app_platform_input, 4, 1)

        card_layout.addLayout(grid)

        btn_layout = QHBoxLayout()
        
        self.start_button = QPushButton("🚀 Start Process")
        self.start_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5DB0FF, stop:1 #2D8CFF);
                color: white;
                padding: 12px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background: #4CA0EE; }
            QPushButton:disabled { background: #CCCCCC; }
        """)
        self.start_button.clicked.connect(self.start_process)
        btn_layout.addWidget(self.start_button)

        self.copy_button = QPushButton("📋 Copy")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_credentials)
        btn_layout.addWidget(self.copy_button)

        card_layout.addLayout(btn_layout)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setRange(0, 1)
        card_layout.addWidget(self.progress)

        self.result_label = QLabel("⏳ Ready to start...")
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("""
            QLabel {
                background: white;
                padding: 12px;
                border-radius: 8px;
                border: 1px solid #e1e4e8;
                font-family: monospace;
            }
        """)
        self.result_label.setMinimumHeight(80)
        card_layout.addWidget(self.result_label)

        card_layout.addWidget(QLabel("📊 Activity Log:"))
        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setStyleSheet("""
            QTextEdit {
                background: white;
                border-radius: 8px;
                border: 1px solid #e1e4e8;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        card_layout.addWidget(self.log_panel)

        layout.addWidget(card)

        footer = QLabel("⚠️ Using advanced methods to extract API credentials")
        footer.setStyleSheet("color: #666; font-size: 10px; padding: 5px;")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)

    def start_process(self):
        phone = self.phone_input.text().strip()
        title = self.app_title_input.text().strip()
        shortname = self.app_shortname_input.text().strip()
        url = self.app_url_input.text().strip()
        platform = self.app_platform_input.currentText()

        if not all([phone, title, shortname, url]):
            QMessageBox.warning(self, "Validation Error", "Please fill in all required fields.")
            return

        self.start_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.result_label.setText("🔄 Starting process...")
        self.log_panel.clear()

        self.worker = WorkerThread(phone, title, shortname, url, platform)
        self.worker.append_log.connect(self.append_log)
        self.worker.update_result.connect(self.on_result)
        self.worker.show_message.connect(self.show_message_box)
        self.worker.set_running.connect(self.on_set_running)
        self.worker.set_progress.connect(self.on_set_progress)
        self.worker.request_code_input.connect(self.request_verification_code)
        self.worker.start()

    def request_verification_code(self, phone):
        code, ok = QInputDialog.getText(
            self, 
            "Verification Code", 
            f"A confirmation code has been sent to {phone}. Please enter it:",
            QLineEdit.Normal
        )
        
        if ok and code.strip():
            self.worker.set_verification_code(code.strip())
            self.log_panel.append(f"[{time.strftime('%H:%M:%S')}] Verification code entered")
        else:
            self.worker.set_verification_code(None)

    def on_result(self, text):
        self.current_credentials = text
        self.result_label.setText(text)
        self.copy_button.setEnabled(True)

    def append_log(self, text):
        self.log_panel.append(f"[{time.strftime('%H:%M:%S')}] {text}")

    def show_message_box(self, title, message):
        if title.lower() == "success":
            QMessageBox.information(self, title, message)
        else:
            QMessageBox.critical(self, title, message)

    def on_set_running(self, running):
        self.start_button.setEnabled(not running)
        if not running:
            self.progress.setRange(0, 1)

    def on_set_progress(self, min_val, max_val):
        if min_val == 0 and max_val == 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(min_val, max_val)

    def copy_credentials(self):
        if self.current_credentials:
            try:
                pyperclip.copy(self.current_credentials)
                QMessageBox.information(self, "Copied", "Credentials copied to clipboard!")
            except:
                QApplication.clipboard().setText(self.current_credentials)
                QMessageBox.information(self, "Copied", "Credentials copied to clipboard!")

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = TelegramAPIGetter()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
#Coded by Arian Lavi
import time
import random
import string
import sys
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# UI Libraries
from rich.console import Console
from rich.panel import Panel
from rich.progress import track
from rich.layout import Layout
from rich.align import Align
from rich.text import Text
from pyfiglet import Figlet

# Initialize Console
console = Console()

class TelegramAppBot:
    def __init__(self):
        self.base_url = "http://my.telegram.org"
        self.driver = None
        self.wait = None

    def render_banner(self):
        """Renders the ASCII art header."""
        os.system('cls' if os.name == 'nt' else 'clear')
        f = Figlet(font='slant')
        title = f.renderText('TG  TOOLS')
        
        console.print(Panel(
            Align.center(Text(title, style="bold cyan")),
            border_style="blue",
            title="[bold white]Automator v2.0[/bold white]",
            subtitle="[dim]Coded by Arian Lavi[/dim]"
        ))

    def setup_driver(self):
        """Initializes Chrome with clean logging."""
        with console.status("[bold green]Initializing WebDriver engine...[/bold green]", spinner="dots"):
            options = webdriver.ChromeOptions()
            options.add_argument("--log-level=3")
            options.add_argument("--start-maximized")
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            
            try:
                self.driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()), 
                    options=options
                )
                self.wait = WebDriverWait(self.driver, 20)
                console.log("[green]Driver hooked successfully.[/green]")
            except Exception as e:
                console.log(f"[red]Failed to launch driver: {e}[/red]")
                sys.exit(1)

    def generate_hash(self, length=20):
        # Logic from original source: alphanumeric random string
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

    def await_user_interaction(self):
        """Pauses execution for manual 2FA."""
        
        instructions = """
[bold yellow]ATTENTION REQUIRED[/bold yellow]

1. Browser is now open at [underline]my.telegram.org[/underline]
2. Enter your phone number & confirmation code manually.
3. Navigate to [bold]API development tools[/bold].
4. Stop when you see the 'Create new application' form.
        """
        
        console.print(Panel(instructions, title="Waiting for User", border_style="yellow"))
        console.input("\n[bold blink]>> Press [ENTER] once you are on the Form page...[/bold blink]")

    def process_form(self):
        """Injects data and submits."""
        try:
            console.rule("[bold blue]Starting Injection Phase[/bold blue]")
            
            # Generating payloads
            app_title = self.generate_hash()
            app_short = self.generate_hash()
            
            console.log(f"[cyan]➜ Generated Title:[/cyan] [bold]{app_title}[/bold]")
            console.log(f"[cyan]➜ Generated Hash :[/cyan] [bold]{app_short}[/bold]")

            # Targeting elements
            # Logic matches source: fills input fields
            t_input = self.wait.until(EC.visibility_of_element_located((By.NAME, 'app_title')))
            s_input = self.driver.find_element(By.NAME, 'app_shortname')
            
            t_input.clear()
            t_input.send_keys(app_title)
            s_input.clear()
            s_input.send_keys(app_short)
            console.log("[green] Form fields populated.[/green]")

            # Platform selection (Index 7)
            # Logic matches source: selects 8th radio button
            platforms = self.driver.find_elements(By.NAME, 'app_platform')
            if len(platforms) > 7:
                platforms[7].click()
                console.log("[green] Platform 'Other' selected.[/green]")
            else:
                console.log("[red]! Warning: Platform list mismatch. Selecting default.[/red]")
                platforms[-1].click()

            # Safety Delay with Visual Progress Bar
            # Logic matches source: 5000ms timeout
            for _ in track(range(5), description="[bold yellow]Safety Delay (Anti-Flood)...[/bold yellow]"):
                time.sleep(1)

            # Execution
            console.log("[bold magenta]>>> Executing createApp() JS payload...[/bold magenta]")
            self.driver.execute_script("createApp();")
            
            console.print(Panel("[bold green]SUCCESS: Application Created.[/bold green]", border_style="green"))

        except Exception as e:
            console.print_exception()

    def run(self):
        self.render_banner()
        self.setup_driver()
        
        try:
            self.driver.get(self.base_url)
            self.await_user_interaction()
            self.process_form()
            
            console.input("[dim]Press [Enter] to terminate session...[/dim]")
        except KeyboardInterrupt:
            console.print("\n[red]Session aborted by user.[/red]")
        finally:
            if self.driver:
                self.driver.quit()

if __name__ == "__main__":
    bot = TelegramAppBot()
    bot.run()
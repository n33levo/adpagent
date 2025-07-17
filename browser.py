#!/usr/bin/env python3
"""
Browser automation for ADP Resume Downloader
"""

import asyncio
from typing import List, Optional
from playwright.async_api import async_playwright, Page, Browser
from bs4 import BeautifulSoup

from config import CONFIG, LOGGER
from models import BrowserState, LoginStatus, CandidateModel

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.context = None

    async def setup_browser(self) -> BrowserState:
        try:
            LOGGER.info("Setting up browser")
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=CONFIG.browser.headless
            )
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            
            LOGGER.info("Browser setup completed")
            return BrowserState(is_setup=True)
        except Exception as e:
            LOGGER.error(f"Browser setup failed: {str(e)}")
            return BrowserState(is_setup=False, error_message=str(e))

    async def navigate_to_login(self, login_url: str) -> BrowserState:
        try:
            LOGGER.info(f"Navigating to login page: {login_url}")
            await self.page.goto(login_url)
            await self.page.wait_for_load_state('networkidle')
            
            return BrowserState(
                is_setup=True,
                current_url=self.page.url
            )
        except Exception as e:
            LOGGER.error(f"Navigation failed: {str(e)}")
            return BrowserState(error_message=str(e))

    async def attempt_login(self, username: str, password: str) -> tuple[LoginStatus, BrowserState]:
        try:
            LOGGER.info("Attempting ADP login")
            
            # Check if already logged in
            if await self._is_logged_in():
                LOGGER.info("Already logged in")
                return LoginStatus.SUCCESS, BrowserState(
                    is_setup=True,
                    current_url=self.page.url,
                    is_logged_in=True,
                    login_status=LoginStatus.SUCCESS
                )
            
            # Wait for page to fully load and take initial screenshot
            await asyncio.sleep(3)
            await self.page.screenshot(path="login_page_initial.png")
            LOGGER.info("Initial screenshot saved: login_page_initial.png")
            
            # Log all input fields on the page for debugging
            all_inputs = await self.page.query_selector_all('input')
            LOGGER.info(f"Found {len(all_inputs)} input fields on the page")
            for i, input_field in enumerate(all_inputs):
                try:
                    tag_name = await input_field.evaluate('el => el.tagName')
                    input_type = await input_field.get_attribute('type') or 'no-type'
                    input_name = await input_field.get_attribute('name') or 'no-name'
                    input_id = await input_field.get_attribute('id') or 'no-id'
                    placeholder = await input_field.get_attribute('placeholder') or 'no-placeholder'
                    LOGGER.info(f"Input {i}: {tag_name} type='{input_type}' name='{input_name}' id='{input_id}' placeholder='{placeholder}'")
                except:
                    LOGGER.info(f"Input {i}: Could not get attributes")
            
            # Step 1: Find User ID field with ADP-specific selectors (based on actual HTML)
            user_id_selectors = [
                'sdf-input#login-form_username',  # Exact match from HTML
                'sdf-input[id="login-form_username"]',  # Alternative syntax
                'sdf-input[label="User ID"]',  # Match by label
                'sdf-input',  # Any sdf-input element
                '#login-form_username',  # By ID
                'input[type="text"]',  # Fallback to regular input
                'input[autocomplete="username"]',  # Match by autocomplete
                'input',  # Last resort
            ]
            
            user_field = None
            for i, selector in enumerate(user_id_selectors):
                try:
                    LOGGER.info(f"Trying selector {i+1}/{len(user_id_selectors)}: {selector}")
                    user_field = await self.page.wait_for_selector(selector, timeout=3000)
                    if user_field:
                        LOGGER.info(f"Found user field with selector: {selector}")
                        # Verify this is a visible, editable field
                        is_visible = await user_field.is_visible()
                        is_enabled = await user_field.is_enabled()
                        LOGGER.info(f"Field visible: {is_visible}, enabled: {is_enabled}")
                        if is_visible and is_enabled:
                            break
                        else:
                            user_field = None
                except Exception as e:
                    LOGGER.info(f"Selector {selector} failed: {str(e)}")
                    continue
            
            if not user_field:
                LOGGER.error("Could not find User ID field after trying all selectors")
                await self.page.screenshot(path="no_user_field_found.png")
                LOGGER.info("Screenshot saved: no_user_field_found.png")
                return LoginStatus.FAILED, BrowserState(error_message="User ID field not found")
            
            LOGGER.info("Entering User ID")
            
            # For sdf-input custom elements, we need to trigger validation events
            element_tag = await user_field.evaluate('el => el.tagName.toLowerCase()')
            LOGGER.info(f"Found element type: {element_tag}")
            
            if element_tag == 'sdf-input':
                # For custom sdf-input elements, we need to properly interact with the shadow DOM
                try:
                    LOGGER.info("Handling ADP sdf-input custom element")
                    
                    # First, check if this element has a shadow root and find the actual input
                    actual_input = await user_field.evaluate('''
                        el => {
                            // Check if there's a shadow root
                            if (el.shadowRoot) {
                                const input = el.shadowRoot.querySelector('input');
                                if (input) {
                                    console.log('Found input in shadow DOM');
                                    return 'shadow';
                                }
                            }
                            // Check if there's a direct child input
                            const input = el.querySelector('input');
                            if (input) {
                                console.log('Found direct child input');
                                return 'child';
                            }
                            // Check if this element itself accepts input
                            if (el.hasAttribute('value') || el.value !== undefined) {
                                console.log('Element itself accepts input');
                                return 'direct';
                            }
                            return 'unknown';
                        }
                    ''')
                    
                    LOGGER.info(f"sdf-input structure: {actual_input}")
                    
                    # Click to focus the element first
                    await user_field.click()
                    await asyncio.sleep(0.5)
                    
                    # Method 1: Try to interact with shadow DOM input if it exists
                    if actual_input == 'shadow':
                        LOGGER.info("Entering text via shadow DOM input")
                        await user_field.evaluate(f'''
                            el => {{
                                const input = el.shadowRoot.querySelector('input');
                                if (input) {{
                                    input.focus();
                                    input.value = '';
                                    input.value = '{username}';
                                    
                                    // Trigger events on both the inner input and the custom element
                                    ['focus', 'input', 'change', 'blur'].forEach(eventType => {{
                                        input.dispatchEvent(new Event(eventType, {{ bubbles: true }}));
                                        el.dispatchEvent(new Event(eventType, {{ bubbles: true }}));
                                    }});
                                    
                                    // Trigger keyboard events
                                    input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Tab', bubbles: true }}));
                                    input.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Tab', bubbles: true }}));
                                }}
                            }}
                        ''')
                    
                    # Method 2: Try typing character by character to trigger real events
                    else:
                        LOGGER.info("Using character-by-character typing with enhanced events")
                        # Clear field first
                        await user_field.evaluate('el => { if (el.value !== undefined) el.value = ""; }')
                        
                        # Type each character with events
                        for char in username:
                            await user_field.type(char, delay=50)
                            # Trigger additional validation events after each character
                            await user_field.evaluate('''
                                el => {
                                    el.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
                                    if (el.shadowRoot) {
                                        const input = el.shadowRoot.querySelector('input');
                                        if (input) {
                                            input.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
                                        }
                                    }
                                }
                            ''')
                            await asyncio.sleep(50)
                    
                    # Final validation trigger - simulate all events that could trigger validation
                    await user_field.evaluate(f'''
                        el => {{
                            // Set the value multiple ways to ensure it sticks
                            if (el.shadowRoot) {{
                                const input = el.shadowRoot.querySelector('input');
                                if (input) {{
                                    input.value = '{username}';
                                }}
                            }}
                            if (el.value !== undefined) {{
                                el.value = '{username}';
                            }}
                            
                            // Trigger comprehensive event chain
                            const events = ['input', 'change', 'blur', 'focusout', 'keyup'];
                            events.forEach(eventType => {{
                                el.dispatchEvent(new Event(eventType, {{ bubbles: true, cancelable: true }}));
                                // Also trigger on shadow DOM input if it exists
                                if (el.shadowRoot) {{
                                    const input = el.shadowRoot.querySelector('input');
                                    if (input) {{
                                        input.dispatchEvent(new Event(eventType, {{ bubbles: true, cancelable: true }}));
                                    }}
                                }}
                            }});
                            
                            // Trigger custom events that ADP might be listening for
                            el.dispatchEvent(new CustomEvent('validate', {{ bubbles: true, detail: {{ value: '{username}' }} }}));
                            el.dispatchEvent(new CustomEvent('valueChanged', {{ bubbles: true, detail: {{ value: '{username}' }} }}));
                        }}
                    ''')
                    
                    LOGGER.info("Entered username with comprehensive event validation")
                    
                except Exception as e:
                    LOGGER.error(f"Failed to enter username properly: {str(e)}")
                    # Final fallback: try direct value setting with basic events
                    await user_field.evaluate(f'''
                        el => {{
                            el.value = "{username}";
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                    ''')
            else:
                # Regular input element
                await user_field.clear()
                await user_field.fill(username)
                LOGGER.info("Set value using standard fill method")
            
            # Wait for validation to complete and button to become enabled
            await asyncio.sleep(3)
            
            # Enhanced check for Next button enabling
            next_button_enabled = False
            for attempt in range(5):  # Try 5 times with increasing waits
                try:
                    # Look for the Next button with multiple approaches
                    next_buttons = await self.page.query_selector_all('sdf-button, button')
                    for button in next_buttons:
                        try:
                            button_text = await button.text_content()
                            if button_text and 'next' in button_text.lower():
                                is_enabled = await button.is_enabled()
                                has_disabled_attr = await button.get_attribute('disabled')
                                aria_disabled = await button.get_attribute('aria-disabled')
                                
                                # Check multiple ways the button could be disabled
                                button_actually_enabled = (
                                    is_enabled and 
                                    not has_disabled_attr and 
                                    aria_disabled != 'true'
                                )
                                
                                LOGGER.info(f"Attempt {attempt+1}: Next button enabled: {is_enabled}, disabled attr: {has_disabled_attr}, aria-disabled: {aria_disabled}, actually enabled: {button_actually_enabled}")
                                
                                if button_actually_enabled:
                                    next_button_enabled = True
                                    break
                        except:
                            continue
                    
                    if next_button_enabled:
                        break
                    
                    # If button still not enabled, try more aggressive validation triggering
                    if attempt < 4:
                        LOGGER.info(f"Button not enabled yet, triggering more events (attempt {attempt+1})")
                        await user_field.evaluate(f'''
                            el => {{
                                // Focus and blur to trigger validation
                                el.focus();
                                
                                // Set value again to ensure it's there
                                if (el.shadowRoot) {{
                                    const input = el.shadowRoot.querySelector('input');
                                    if (input) {{
                                        input.value = '{username}';
                                        input.focus();
                                        input.blur();
                                    }}
                                }}
                                
                                // Trigger form validation events
                                const form = el.closest('form');
                                if (form) {{
                                    form.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                }}
                                
                                // Trigger tab key to move focus (often triggers validation)
                                el.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Tab', keyCode: 9, bubbles: true }}));
                                el.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Tab', keyCode: 9, bubbles: true }}));
                                
                                // Trigger validation-related custom events
                                el.dispatchEvent(new CustomEvent('validation', {{ bubbles: true }}));
                                el.dispatchEvent(new CustomEvent('fieldValidation', {{ bubbles: true }}));
                            }}
                        ''')
                        await asyncio.sleep(2)
                
                except Exception as e:
                    LOGGER.error(f"Error checking button status: {str(e)}")
                    
            LOGGER.info(f"Final Next button enabled status: {next_button_enabled}")
            
            # Take a screenshot to see current state
            await self.page.screenshot(path="after_username.png")
            LOGGER.info("Screenshot taken after entering username: after_username.png")
            
            # Debug: Log current DOM state and form validation
            await self._debug_form_state()
            
            # Click Next button (from ADP screenshot - there's a "Next" button visible)
            LOGGER.info("Looking for Next button...")
            all_buttons = await self.page.query_selector_all('button')
            LOGGER.info(f"Found {len(all_buttons)} buttons on the page")
            for i, button in enumerate(all_buttons):
                try:
                    button_text = await button.text_content()
                    button_type = await button.get_attribute('type') or 'no-type'
                    button_class = await button.get_attribute('class') or 'no-class'
                    LOGGER.info(f"Button {i}: text='{button_text}' type='{button_type}' class='{button_class}'")
                except:
                    LOGGER.info(f"Button {i}: Could not get attributes")
            
            next_selectors = [
                'sdf-button:has-text("Next")',  # ADP custom button component
                'sdf-button[type="submit"]',  # ADP submit button
                'button:text("Next")',  # Exact text match for Playwright
                'button:has-text("Next")',  # Contains text
                'input[value="Next"]',
                'button[type="submit"]',
                'sdf-button',  # Any ADP button as fallback
                'button',  # Try any button as fallback
                '.next-button',
                '#nextButton'
            ]
            
            next_button = None
            for i, selector in enumerate(next_selectors):
                try:
                    LOGGER.info(f"Trying Next button selector {i+1}/{len(next_selectors)}: {selector}")
                    buttons = await self.page.query_selector_all(selector)
                    
                    for button in buttons:
                        try:
                            is_visible = await button.is_visible()
                            button_text = await button.text_content()
                            
                            # Check if this is actually a Next button
                            if button_text and 'next' in button_text.lower() and is_visible:
                                # For sdf-button, check multiple ways it could be enabled
                                button_tag = await button.evaluate('el => el.tagName.toLowerCase()')
                                
                                if button_tag == 'sdf-button':
                                    # Custom ADP button - check enabled status more thoroughly
                                    is_enabled = await button.evaluate('''
                                        el => {
                                            // Check multiple properties that could indicate enabled state
                                            const disabled = el.disabled || el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true';
                                            const hasClickHandler = el.onclick || el.addEventListener;
                                            
                                            console.log('Button disabled:', disabled);
                                            console.log('Button has click handler:', !!hasClickHandler);
                                            
                                            return !disabled;
                                        }
                                    ''')
                                else:
                                    # Regular button
                                    is_enabled = await button.is_enabled()
                                
                                LOGGER.info(f"Found button with selector: {selector}, text: '{button_text}', visible: {is_visible}, enabled: {is_enabled}")
                                
                                if is_enabled:
                                    next_button = button
                                    break
                                else:
                                    # Even if not enabled, keep this as a fallback
                                    if not next_button:
                                        next_button = button
                        except Exception as e:
                            LOGGER.info(f"Error checking button: {str(e)}")
                            continue
                    
                    if next_button:
                        # Check if we found an enabled button
                        is_enabled = await next_button.is_enabled() if await next_button.evaluate('el => el.tagName.toLowerCase()') != 'sdf-button' else await next_button.evaluate('el => !el.disabled && !el.hasAttribute("disabled")')
                        if is_enabled:
                            break
                        
                except Exception as e:
                    LOGGER.info(f"Next button selector {selector} failed: {str(e)}")
                    continue
            
            if next_button:
                # Try to click the button even if it appears disabled - sometimes ADP buttons work anyway
                try:
                    button_tag = await next_button.evaluate('el => el.tagName.toLowerCase()')
                    button_text = await next_button.text_content()
                    
                    LOGGER.info(f"Attempting to click {button_tag} button with text: '{button_text}'")
                    
                    if button_tag == 'sdf-button':
                        # For ADP custom buttons, try multiple click methods
                        LOGGER.info("Using enhanced click for sdf-button")
                        
                        # Method 1: Try regular click
                        try:
                            await next_button.click()
                            LOGGER.info("Regular click succeeded")
                        except Exception as e:
                            LOGGER.info(f"Regular click failed: {str(e)}, trying JavaScript click")
                            
                            # Method 2: JavaScript click
                            await next_button.evaluate('el => el.click()')
                            
                        # Method 3: Dispatch click event
                        await next_button.evaluate('''
                            el => {
                                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                            }
                        ''')
                    else:
                        # Regular button
                        await next_button.click()
                    
                    LOGGER.info("Successfully clicked Next button")
                    await self.page.wait_for_load_state("networkidle", timeout=15000)
                    await asyncio.sleep(5)  # Give more time for the page to transition
                    
                except Exception as e:
                    LOGGER.error(f"Failed to click Next button: {str(e)}")
                    # Try pressing Enter on the user field as fallback
                    await user_field.press("Enter")
                
                # Take screenshot after clicking Next
                await self.page.screenshot(path="after_next_click.png")
                LOGGER.info("Screenshot taken after clicking Next: after_next_click.png")
            else:
                LOGGER.warning("No Next button found, trying to press Enter on user field")
                await user_field.press("Enter")
                await asyncio.sleep(3)
            
            # Step 2: Enter Password
            password_selectors = [
                'input[name="PASSWORD"]',
                'input[name="password"]',
                'input[type="password"]',
                'input[id="PASSWORD"]',
                'input[id="password"]',
                '#passwordInput'
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = await self.page.wait_for_selector(selector, timeout=10000)
                    if password_field:
                        break
                except:
                    continue
            
            if not password_field:
                LOGGER.error("Could not find password field after entering User ID")
                await self.page.screenshot(path="login_debug.png")
                LOGGER.info("Screenshot saved as login_debug.png for debugging")
                return LoginStatus.FAILED, BrowserState(error_message="Password field not found")
            
            LOGGER.info("Entering password")
            await password_field.fill(password)
            await asyncio.sleep(1)
            
            # Submit login form
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Sign In")',
                'button:has-text("Login")',
                'button:has-text("Submit")',
                '.submit-button',
                '#submitButton'
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = await self.page.wait_for_selector(selector, timeout=3000)
                    if submit_button:
                        break
                except:
                    continue
            
            if submit_button:
                LOGGER.info("Submitting login form")
                await submit_button.click()
            else:
                LOGGER.info("No submit button found, pressing Enter")
                await password_field.press("Enter")
            
            # Wait for login to complete
            await asyncio.sleep(5)
            await self.page.wait_for_load_state("networkidle")
            
            # Verify login success
            if await self._is_logged_in():
                LOGGER.info("Login successful")
                return LoginStatus.SUCCESS, BrowserState(
                    is_setup=True,
                    current_url=self.page.url,
                    is_logged_in=True,
                    login_status=LoginStatus.SUCCESS
                )
            else:
                LOGGER.error("Login failed - still on login page")
                await self.page.screenshot(path="login_failed.png")
                LOGGER.info("Screenshot saved as login_failed.png for debugging")
                return LoginStatus.FAILED, BrowserState(
                    is_setup=True,
                    current_url=self.page.url,
                    login_status=LoginStatus.FAILED,
                    error_message="Login failed"
                )
                
        except Exception as e:
            LOGGER.error(f"Login error: {str(e)}")
            await self.page.screenshot(path="login_error.png")
            return LoginStatus.FAILED, BrowserState(error_message=str(e))

    async def navigate_to_candidates(self) -> tuple[bool, list]:
        try:
            LOGGER.info("Navigating to candidates page")
            
            # Try common navigation patterns
            navigation_selectors = [
                'a[href*="candidate"]',
                'a[href*="resume"]',
                'a[href*="talent"]',
                'a[href*="recruit"]',
                '.menu-item:has-text("Candidates")',
                '.nav-link:has-text("Resumes")'
            ]
            
            for selector in navigation_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=5000)
                    if element:
                        await element.click()
                        await self.page.wait_for_load_state('networkidle')
                        if await self.is_candidates_page():
                            return True, []
                except:
                    continue
            
            return False, []
            
        except Exception as e:
            LOGGER.error(f"Navigation error: {str(e)}")
            return False, []

    async def extract_candidates_from_page(self) -> List[CandidateModel]:
        try:
            LOGGER.info("Extracting candidates from current page")
            candidates = []
            
            # Common selectors for candidate listings
            candidate_selectors = [
                '.candidate-item',
                '.employee-row',
                '.person-card',
                'tr[data-candidate-id]',
                '[data-employee-id]'
            ]
            
            for selector in candidate_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    if elements:
                        for i, element in enumerate(elements):
                            try:
                                # Extract name
                                name_text = await element.text_content() or f"Candidate_{i+1}"
                                name = name_text.strip().split('\n')[0][:50]
                                
                                # Extract profile link
                                link_element = await element.query_selector('a')
                                if link_element:
                                    href = await link_element.get_attribute('href')
                                    if href:
                                        if href.startswith('/'):
                                            url = f"{self.page.url.split('/')[0]}//{self.page.url.split('/')[2]}{href}"
                                        else:
                                            url = href
                                        
                                        candidate = CandidateModel(
                                            id=f"candidate_{len(candidates)+1}",
                                            name=name,
                                            url=url
                                        )
                                        candidates.append(candidate)
                            except:
                                continue
                        break
                except:
                    continue
            
            LOGGER.info(f"Found {len(candidates)} candidates")
            return candidates
            
        except Exception as e:
            LOGGER.error(f"Candidate extraction error: {str(e)}")
            return []

    async def navigate_to_next_page(self) -> bool:
        try:
            next_selectors = [
                'a:has-text("Next")',
                'button:has-text("Next")',
                '.pagination-next',
                '[aria-label="Next page"]'
            ]
            
            for selector in next_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=2000)
                    if element and await element.is_enabled():
                        await element.click()
                        await self.page.wait_for_load_state('networkidle')
                        return True
                except:
                    continue
            
            return False
            
        except Exception:
            return False

    async def is_candidates_page(self) -> bool:
        try:
            # Check for common indicators of a candidates page
            indicators = ['candidate', 'resume', 'employee', 'talent']
            page_content = await self.page.content()
            return any(indicator in page_content.lower() for indicator in indicators)
        except:
            return False

    async def _is_logged_in(self) -> bool:
        """
        Checks if user is successfully logged in by looking for post-login indicators.
        
        Returns:
            bool: True if logged in, False if still on login page
        """
        try:
            current_url = self.page.url
            LOGGER.info(f"Current URL: {current_url}")
            
            # Check if we're still on login pages (these indicate NOT logged in)
            login_indicators = [
                'signin.adp.com',
                'online.adp.com/signin',
                '/login',
                '/signin',
                'User ID',
                'Password',
                'Sign In'
            ]
            
            # If URL contains login indicators, we're NOT logged in
            for indicator in login_indicators[:5]:  # URL checks
                if indicator in current_url:
                    LOGGER.info(f"Still on login page (URL contains: {indicator})")
                    return False
            
            # Check page content for login indicators
            page_content = await self.page.content()
            for indicator in login_indicators[5:]:  # Content checks
                if indicator in page_content:
                    LOGGER.info(f"Still on login page (page contains: {indicator})")
                    return False
            
            # Look for positive indicators that we're logged in
            success_indicators = [
                'dashboard',
                'workforce',
                'home',
                'employee',
                'menu',
                'navigation',
                'logout',
                'sign out'
            ]
            
            # Check URL for success indicators
            for indicator in success_indicators:
                if indicator.lower() in current_url.lower():
                    LOGGER.info(f"Login detected (URL contains: {indicator})")
                    return True
            
            # Check page content for success indicators
            for indicator in success_indicators:
                if indicator.lower() in page_content.lower():
                    LOGGER.info(f"Login detected (page contains: {indicator})")
                    return True
            
            # If we've navigated away from signin domains, probably logged in
            if 'signin' not in current_url and 'login' not in current_url:
                LOGGER.info("Login detected (navigated away from login domain)")
                return True
            
            LOGGER.info("Login status unclear - assuming not logged in")
            return False
            
        except Exception as e:
            LOGGER.error(f"Error checking login status: {str(e)}")
            return False

    async def cleanup(self) -> None:
        try:
            LOGGER.info("Cleaning up browser resources")
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            LOGGER.error(f"Cleanup error: {str(e)}")

# Alias for compatibility
BrowserAutomation = BrowserManager

import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# Configuration
USERNAME = input("Enter your email address:")
PASSWORD = input("Enter your password:")
BASE_URL = "https://islands.smp.uq.edu.au"


def extract_resident_info(soup):
    """Extracts resident information including first pregnancy details"""
    info = {
        "name": "Unknown",
        "current_address": "Unknown",
        "current_age": None,
        "first_pregnancy_year": None,
        "age_at_first_pregnancy": None,
        "pregnancy_details": "",
    }

    # Name detection with multiple fallbacks
    name_selectors = [
        "h2.islander-name",
        "h1.profile-title",
        "div.profile-header h2",
        "title",
    ]

    for selector in name_selectors:
        try:
            tag = soup.select_one(selector)
            if tag:
                info["name"] = tag.get_text(strip=True)
                if selector == "title":
                    info["name"] = info["name"].split("|")[0].strip()
                break
        except:
            continue

    if info["name"] == "Unknown":
        return None

    # Process timeline events
    current_age = None
    max_age = None
    address_history = []
    first_pregnancy_found = False
    timeline_rows = soup.select("div#t1 table tr")

    for row in timeline_rows:
        cells = row.find_all(["th", "td"])

        # Age headers
        if (
            len(cells) == 1
            and cells[0].get("colspan") == "2"
            and "Age" in cells[0].text
        ):
            try:
                current_age = int(cells[0].text.split()[1])
                max_age = current_age  # Track highest age for current age
            except:
                current_age = None
            continue

        if len(cells) < 2:
            continue

        date_cell, event_cell = cells[0], cells[1]

        # Track address changes
        if "Moved to" in event_cell.text:
            try:
                address = event_cell.text.split("Moved to")[1].split("with")[0].strip()
                address_history.append(address)
            except:
                pass

        # Detect FIRST pregnancy only
        if current_age and "Pregnant" in event_cell.text and not first_pregnancy_found:
            try:
                info.update(
                    {
                        "first_pregnancy_year": (
                            date_cell.text.split("/")[1]
                            if "/" in date_cell.text
                            else "Unknown"
                        ),
                        "age_at_first_pregnancy": current_age,
                        "pregnancy_details": event_cell.get_text(strip=True),
                    }
                )
                first_pregnancy_found = True
            except Exception as e:
                print(f"Error processing pregnancy data: {str(e)}")

    # Set final address and age
    info["current_address"] = address_history[-1] if address_history else "Unknown"
    info["current_age"] = max_age

    return info if first_pregnancy_found else None


def main():
    service = Service(executable_path="chromedriver.exe")
    driver = webdriver.Chrome(service=service)
    wait = WebDriverWait(driver, 20)

    with open(
        "arcadia_pregnancies.csv", mode="w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "Name",
                "Current Address",
                "Current Age",
                "First Pregnancy Year",
                "Age at First Pregnancy",
                "Pregnancy Details",
            ]
        )

        try:
            # Login
            print("Logging in...")
            driver.get(f"{BASE_URL}/login.php")
            wait.until(EC.element_to_be_clickable((By.NAME, "email"))).send_keys(
                USERNAME
            )
            wait.until(EC.element_to_be_clickable((By.NAME, "word"))).send_keys(
                PASSWORD + Keys.ENTER
            )
            wait.until(EC.url_contains("index.php"))
            print("Login successful")

            # Navigate to Arcadia
            print("Going to Arcadia village...")
            driver.get(f"{BASE_URL}/village.php?Arcadia")
            wait.until(EC.presence_of_element_located((By.ID, "villagemap")))

            # Get all house indices
            print("Finding houses...")
            house_indices = driver.execute_script(
                """
                let indices = [];
                document.querySelectorAll('div.house img').forEach(img => {
                    let onclick = img.getAttribute('onclick') || '';
                    let match = onclick.match(/getHouse\((\d+)\)/);
                    if (match) indices.push(parseInt(match[1]));
                });
                return indices;
            """
            )
            print(f"Found {len(house_indices)} houses to process")

            # Process each house
            for index in house_indices:
                print(f"\nProcessing house {index}")
                try:
                    # Open house modal
                    driver.execute_script(f"getHouse({index})")
                    time.sleep(2)

                    # Get all residents
                    residents = wait.until(
                        EC.presence_of_all_elements_located(
                            (By.CSS_SELECTOR, ".resident a")
                        )
                    )
                    resident_urls = [r.get_attribute("href") for r in residents]
                    print(f"Found {len(resident_urls)} residents in house {index}")

                    # Process each resident
                    for url in resident_urls:
                        print(f"Processing resident: {url}")
                        driver.get(url)
                        time.sleep(1)  # Ensure page loads completely

                        soup = BeautifulSoup(driver.page_source, "html.parser")
                        resident_info = extract_resident_info(soup)

                        if (
                            resident_info
                            and "Arcadia" in resident_info["current_address"]
                        ):
                            print(f"Found pregnancy: {resident_info}")
                            writer.writerow(
                                [
                                    resident_info["name"],
                                    resident_info["current_address"],
                                    resident_info["current_age"],
                                    resident_info["first_pregnancy_year"],
                                    resident_info["age_at_first_pregnancy"],
                                    resident_info["pregnancy_details"],
                                ]
                            )
                            file.flush()  # Write immediately

                        # Return to village
                        driver.get(f"{BASE_URL}/village.php?Arcadia")
                        wait.until(
                            EC.presence_of_element_located((By.ID, "villagemap"))
                        )

                        # Reopen same house
                        driver.execute_script(f"getHouse({index})")
                        time.sleep(1)

                    # Return to village after processing house
                    driver.get(f"{BASE_URL}/village.php?Arcadia")
                    time.sleep(1)

                except Exception as e:
                    print(f"Error processing house {index}: {str(e)}")
                    driver.get(f"{BASE_URL}/village.php?Arcadia")
                    continue

        except Exception as e:
            print(f"Fatal error: {str(e)}")
        finally:
            driver.quit()
            print("Scraping complete. Data saved to arcadia_pregnancies.csv")


if __name__ == "__main__":
    main()

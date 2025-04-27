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
USERNAME = "mfox@olin.edu"
PASSWORD = "Hfghdhdth1?"
BASE_URL = "https://islands.smp.uq.edu.au"


def extract_resident_info(soup):
    """Fixed pregnancy detection that works with Krisha's example"""
    info = {
        "name": "Unknown",
        "address": "Unknown",
        "pregnancy_year": None,
        "age_at_pregnancy": None,
        "pregnancy_details": "",
    }

    # Name detection
    name_tag = soup.find("h2") or soup.find("h1") or soup.find("title")
    if name_tag:
        info["name"] = name_tag.get_text(strip=True)
        if name_tag.name == "title":
            info["name"] = info["name"].split("|")[0].strip()
        print(f"Found name: {info['name']}")
    else:
        print("Warning: Could not determine resident name")
        return None

    # Process timeline
    current_age = None
    current_address = "Unknown"
    timeline_rows = soup.select("div#t1 table tr")

    for row in timeline_rows:
        cells = row.find_all(["th", "td"])

        # Age headers (single cell with colspan="2")
        if (
            len(cells) == 1
            and cells[0].get("colspan") == "2"
            and "Age" in cells[0].text
        ):
            try:
                current_age = int(cells[0].text.split()[1])
                print(f"Current age: {current_age}")
            except:
                current_age = None
            continue

        # Need at least date and event cells
        if len(cells) < 2:
            continue

        date_cell, event_cell = cells[0], cells[1]

        # Track address changes
        if "Moved to" in event_cell.text:
            try:
                address = event_cell.text.split("Moved to")[1].split("with")[0].strip()
                current_address = address
                print(f"Current address: {current_address}")
            except:
                pass

        # Detect pregnancy
        if current_age and current_age < 18 and "Pregnant" in event_cell.text:
            try:
                date_parts = date_cell.text.split("/")
                info.update(
                    {
                        "pregnancy_year": (
                            date_parts[1] if len(date_parts) == 2 else "Unknown"
                        ),
                        "age_at_pregnancy": current_age,
                        "pregnancy_details": event_cell.get_text(strip=True),
                        "address": current_address,
                    }
                )
                print(f"Pregnancy found at age {current_age}")
                return info
            except Exception as e:
                print(f"Error processing pregnancy data: {str(e)}")

    print("No pregnancy found under age 18")
    return None


def main():
    service = Service(executable_path="chromedriver.exe")
    driver = webdriver.Chrome(service=service)
    wait = WebDriverWait(driver, 20)

    with open(
        "pregnancies_under_18.csv", mode="w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.writer(file)
        writer.writerow(["Name", "Address", "Year", "Age", "Details"])

        try:
            # Login
            driver.get(f"{BASE_URL}/login.php")
            wait.until(EC.element_to_be_clickable((By.NAME, "email"))).send_keys(
                USERNAME
            )
            wait.until(EC.element_to_be_clickable((By.NAME, "word"))).send_keys(
                PASSWORD + Keys.ENTER
            )
            wait.until(EC.url_contains("index.php"))

            # Navigate to village
            driver.get(f"{BASE_URL}/village.php?Arcadia")
            wait.until(EC.presence_of_element_located((By.ID, "villagemap")))

            # Get house indices
            house_indices = driver.execute_script(
                """
                let indices = [];
                document.querySelectorAll('div.house--small img').forEach(img => {
                    let match = (img.onclick?.toString() || '').match(/getHouse\((\d+)\)/);
                    if (match) indices.push(parseInt(match[1]));
                });
                return indices;
            """
            )

            # Process houses
            for index in house_indices:
                try:
                    driver.execute_script(f"getHouse({index})")
                    time.sleep(2)

                    residents = wait.until(
                        EC.presence_of_all_elements_located(
                            (By.CSS_SELECTOR, ".resident a")
                        )
                    )
                    resident_urls = [r.get_attribute("href") for r in residents]

                    for url in resident_urls:
                        driver.get(url)
                        soup = BeautifulSoup(driver.page_source, "html.parser")

                        resident_info = extract_resident_info(soup)
                        if resident_info:
                            writer.writerow(
                                [
                                    resident_info["name"],
                                    resident_info["address"],
                                    resident_info["pregnancy_year"],
                                    resident_info["age_at_pregnancy"],
                                    resident_info["pregnancy_details"],
                                ]
                            )
                            file.flush()

                        driver.back()
                        time.sleep(1)

                    driver.back()
                    time.sleep(1)

                except Exception as e:
                    print(f"Error processing house {index}: {str(e)}")
                    driver.get(f"{BASE_URL}/village.php?Arcadia")
                    continue

        finally:
            driver.quit()
            print("Scraping complete. Data saved to pregnancies_under_18.csv")


if __name__ == "__main__":
    main()

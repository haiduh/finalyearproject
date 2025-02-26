import requests
from bs4 import BeautifulSoup
import json
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

def game(gameName):
    if gameName == "Elden Ring":
        base_url = "eldenring.wiki.fextralife.com"
    elif gameName == "Terraria":
        base_url = "terraria.wiki.gg/wiki"
    return base_url

def scrape_page(user_input, base_url):
    formatted_input = user_input.replace(" ", "+")  
    url = "https://" + base_url + "/" + formatted_input
    print(url)

    try:
        page = requests.get(url)
        page.raise_for_status()  
    except Exception as e:
        print('Error downloading page:', e)
        return None

    soup = BeautifulSoup(page.text, 'html.parser')

    # Locate the main wiki content block
    wiki_content = soup.find('div', {'id': 'wiki-content-block'})
    if not wiki_content:
        print("Could not find the wiki content block.")
        return None

    # Extract all relevant text and other elements like tables and images
    content = wiki_content.find_all(['p', 'li', 'h3', 'strong', 'table', 'img', 'a'])

    if not content:
        print("No relevant content found. The page structure might have changed.")
        return None

    data = {}
    current_section = "General Info"  # Default section in case no specific sections are found

    for tag in content:
        if tag.name == 'p' or tag.name == 'li' or tag.name == 'h3' or tag.name == 'strong':
            text = tag.get_text(strip=True)

            # Skip over empty or unwanted tags
            if not text:
                continue

            # Attempt to categorize based on keyword matches or use a default category
            if "Location" in text or "Where to find" in text:
                current_section = "Location"
            elif "Notes" in text or "Tips" in text:
                current_section = "Notes & Tips"
            elif "Effect" in text:
                current_section = "Effects"
            elif "Strategy" in text or "Boss" in text:
                current_section = "Boss Strategies"
            else:
                current_section = "General Info"
            
            # Append text under the current section
            if current_section:
                if current_section not in data:
                    data[current_section] = []
                data[current_section].append(text)

        # Handle tables (e.g., item stats, enemy stats)
        elif tag.name == 'table':
            table_data = []
            rows = tag.find_all('tr')
            for row in rows:
                cols = row.find_all(['td', 'th'])
                table_row = [col.get_text(strip=True) for col in cols]
                if table_row:
                    table_data.append(table_row)
            if table_data:
                if "Stats" not in data:
                    data["Stats"] = []
                data["Stats"].append(table_data)

        # Handle images (e.g., item images, boss images)
        elif tag.name == 'img':
            img_url = tag.get('src')
            if img_url:
                if "Images" not in data:
                    data["Images"] = []
                data["Images"].append(img_url)

        # Handle links (e.g., references to related items or quests)
        elif tag.name == 'a':
            link = tag.get('href')
            if link:
                if "Links" not in data:
                    data["Links"] = []
                data["Links"].append(link)

    # Check if any sections were collected
    if not data:
        print("No data was collected. The section headers might need to be refined.")
    
    return data


# Game Selection
game_Name = input("Enter the game you are playing: ")
base_url = game(game_Name)

# User input for item or location
user_input = input("Enter the item or location you want to scrape (e.g., Somber Smithing Stone (6)): ")
scraped_data = scrape_page(user_input, base_url)

# Save the scraped data to a JSON file
if scraped_data:
    filename = f"{user_input.replace(' ', '_')}_scraped_data.json"
    with open(filename, 'w', encoding='utf-8') as json_file:
        json.dump(scraped_data, json_file, indent=4, ensure_ascii=False)

    print(f"Scraping complete! Data saved to '{filename}'.")
else:
    print("Failed to scrape the data.")

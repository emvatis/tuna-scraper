#!/usr/bin/env python3
"""
HTML Page Analyzer for Web Scraping

This script helps identify the right selectors for scraping by analyzing HTML pages.
It can download a page from a URL or analyze a local HTML file.

Features:
- Identifies common HTML elements and class names
- Finds potential product containers
- Analyzes sample product items
- Suggests selectors for titles, prices, images, etc.
- Checks for JSON-LD structured data
"""

import argparse
import json
import sys
from collections import Counter

from bs4 import BeautifulSoup

# Import functions from main.py
from main import create_session


def download_page(url, output_file=None):
    """
    Downloads a page from a URL and saves it to a file if output_file is provided.

    Args:
        url: URL to download
        output_file: File to save the HTML to (optional)

    Returns:
        HTML content of the page

    """
    print(f"Downloading page: {url}")
    session = create_session()
    response = session.get(url, timeout=30)
    response.raise_for_status()

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(response.text)
        print(f"Saved HTML to: {output_file}")

    return response.text


def load_html(html_file=None, url=None):
    """
    Loads HTML content from a file or URL.

    Args:
        html_file: Path to a local HTML file
        url: URL to download HTML from

    Returns:
        BeautifulSoup object and source URL

    """
    if not html_file and not url:
        raise ValueError("Either html_file or url must be provided")

    if html_file:
        print(f"Loading HTML from file: {html_file}")
        with open(html_file, encoding="utf-8") as f:
            html_content = f.read()
        source_url = "Local file"
        base_url = "https://www.carrefour.it"  # Default base URL for local files
    else:
        html_content = download_page(url)
        source_url = url
        base_url = url.split("/spesa-online")[0] if "/spesa-online" in url else url

    soup = BeautifulSoup(html_content, "html.parser")
    return soup, base_url


def find_common_elements(soup):
    """
    Finds common HTML elements and class names in the page.

    Args:
        soup: BeautifulSoup object

    Returns:
        Dictionary with common elements and class names

    """
    print("\n=== Common HTML Elements ===")

    # Count tag types
    tag_counter = Counter(tag.name for tag in soup.find_all())
    print("\nMost common HTML tags:")
    for tag, count in tag_counter.most_common(10):
        print(f"  {tag}: {count}")

    # Count class names
    class_counter = Counter()
    for tag in soup.find_all(class_=True):
        for class_name in tag.get("class", []):
            class_counter[class_name] += 1

    print("\nMost common class names:")
    for class_name, count in class_counter.most_common(15):
        print(f"  {class_name}: {count}")

    # Find potential product containers
    potential_containers = []
    product_keywords = ["product", "item", "card", "tile", "article"]

    for class_name, count in class_counter.items():
        if any(keyword in class_name.lower() for keyword in product_keywords) and count > 1:
            potential_containers.append((class_name, count))

    print("\nPotential product containers:")
    for class_name, count in sorted(potential_containers, key=lambda x: x[1], reverse=True):
        print(f"  {class_name}: {count} occurrences")

    return {
        "tags": dict(tag_counter.most_common(10)),
        "classes": dict(class_counter.most_common(15)),
        "potential_containers": dict(potential_containers),
    }


def analyze_product_containers(soup, container_class=None):
    """
    Analyzes potential product containers to find the best one.

    Args:
        soup: BeautifulSoup object
        container_class: Class name to use for product containers (optional)

    Returns:
        List of product containers and the container class used

    """
    print("\n=== Product Container Analysis ===")

    # Try to find product containers
    container_candidates = [
        ("div", "product-item"),
        ("div", "product-card"),
        ("div", "product-tile"),
        ("div", "item"),
        ("article", None),
    ]

    containers = []
    used_container_class = container_class

    if container_class:
        # Use the specified container class
        containers = soup.find_all(class_=container_class)
        print(f"Using specified container class: {container_class}")
        print(f"Found {len(containers)} containers")
    else:
        # Try different container candidates
        for tag, class_name in container_candidates:
            if class_name:
                containers = soup.find_all(tag, class_=lambda x: x and class_name.lower() in x.lower())
            else:
                containers = soup.find_all(tag)

            if containers:
                used_container_class = class_name or tag
                print(
                    f"Found {len(containers)} potential product containers with {tag}"
                    + (f", class containing '{class_name}'" if class_name else "")
                )
                break

    if not containers:
        print("No product containers found. Try specifying a container class.")
        return [], None

    # Analyze the first few containers
    print(f"\nAnalyzing {min(3, len(containers))} sample containers:")
    for i, container in enumerate(containers[:3]):
        print(f"\nContainer {i + 1}:")

        # Check for common product elements
        elements = {
            "title": container.find(
                ["h1", "h2", "h3", "h4", "a"],
                class_=lambda x: x and any(keyword in x.lower() for keyword in ["title", "name", "product"]),
            )
            or container.find("a", class_=lambda x: x and "link" in x.lower()),
            "price": container.find(class_=lambda x: x and "price" in x.lower()),
            "image": container.find("img"),
            "link": container.find("a", href=True),
        }

        for element_type, element in elements.items():
            if element:
                if element_type == "title":
                    print(f"  Title: {element.text.strip()[:50]}...")
                    print(f"    Tag: {element.name}, Class: {element.get('class')}")
                elif element_type == "price":
                    print(f"  Price: {element.text.strip()}")
                    print(f"    Tag: {element.name}, Class: {element.get('class')}")
                elif element_type == "image":
                    print(f"  Image: {element.get('src', element.get('data-src', 'No src'))[:50]}...")
                    print(f"    Tag: {element.name}, Class: {element.get('class')}")
                elif element_type == "link":
                    print(f"  Link: {element.get('href')[:50]}...")
                    print(f"    Tag: {element.name}, Class: {element.get('class')}")
            else:
                print(f"  No {element_type} found")

    return containers, used_container_class


def suggest_selectors(containers):
    """
    Suggests selectors for different product elements based on the containers.

    Args:
        containers: List of product containers

    Returns:
        Dictionary with suggested selectors

    """
    if not containers:
        return {}

    print("\n=== Suggested Selectors ===")

    # Collect all potential selectors
    selectors = {
        "title": [],
        "price": [],
        "image": [],
        "price_per_unit": [],
        "link": [],
    }

    for container in containers[:10]:  # Analyze up to 10 containers
        # Title selectors
        title_candidates = [
            container.find(
                ["h1", "h2", "h3", "h4"],
                class_=lambda x: x and any(keyword in x.lower() for keyword in ["title", "name", "product"]),
            ),
            container.find("a", class_=lambda x: x and "product" in x.lower()),
            container.find("a", class_=lambda x: x and "link" in x.lower()),
            container.find("div", class_=lambda x: x and "name" in x.lower()),
        ]

        for candidate in title_candidates:
            if candidate and candidate.text.strip():
                selector = f"{candidate.name}.{' '.join(candidate.get('class', []))}"
                selectors["title"].append(selector)

        # Price selectors
        price_candidates = [
            container.find(
                class_=lambda x: x
                and "price" in x.lower()
                and not any(keyword in x.lower() for keyword in ["unit", "kg", "per"])
            ),
            container.find("span", class_=lambda x: x and "price" in x.lower()),
            container.find("div", class_=lambda x: x and "price" in x.lower()),
        ]

        for candidate in price_candidates:
            if candidate and candidate.text.strip():
                selector = f"{candidate.name}.{' '.join(candidate.get('class', []))}"
                selectors["price"].append(selector)

        # Price per unit selectors
        price_per_unit_candidates = [
            container.find(class_=lambda x: x and any(keyword in x.lower() for keyword in ["unit", "kg", "per"])),
            container.find("span", class_=lambda x: x and "unit" in x.lower()),
            container.find("div", class_=lambda x: x and "unit" in x.lower()),
        ]

        for candidate in price_per_unit_candidates:
            if candidate and candidate.text.strip():
                selector = f"{candidate.name}.{' '.join(candidate.get('class', []))}"
                selectors["price_per_unit"].append(selector)

        # Image selectors
        image = container.find("img")
        if image:
            selector = f"img.{' '.join(image.get('class', []))}"
            selectors["image"].append(selector)

        # Link selectors
        link = container.find("a", href=True)
        if link:
            selector = f"a.{' '.join(link.get('class', []))}"
            selectors["link"].append(selector)

    # Count occurrences and find most common selectors
    suggested_selectors = {}

    for element_type, selector_list in selectors.items():
        if selector_list:
            counter = Counter(selector_list)
            most_common = counter.most_common(3)

            print(f"\nSuggested {element_type} selectors:")
            for selector, count in most_common:
                print(f"  {selector}: {count} occurrences")

            suggested_selectors[element_type] = [selector for selector, _ in most_common]

    return suggested_selectors


def check_json_ld(soup):
    """
    Checks for JSON-LD structured data in the page.

    Args:
        soup: BeautifulSoup object

    Returns:
        List of JSON-LD objects

    """
    print("\n=== JSON-LD Structured Data ===")

    json_ld_scripts = soup.find_all("script", type="application/ld+json")

    if not json_ld_scripts:
        print("No JSON-LD structured data found")
        return []

    print(f"Found {len(json_ld_scripts)} JSON-LD script tags")

    json_ld_data = []

    for i, script in enumerate(json_ld_scripts):
        try:
            data = json.loads(script.string)
            json_ld_data.append(data)

            print(f"\nJSON-LD #{i + 1}:")

            # Check for product data
            if isinstance(data, dict):
                if data.get("@type") == "Product":
                    print("  Contains product data")
                    print(f"  Product name: {data.get('name')}")
                    if "offers" in data:
                        print(f"  Price: {data.get('offers', {}).get('price')}")
                elif "itemListElement" in data:
                    print(f"  Contains item list with {len(data['itemListElement'])} items")
                    for j, item in enumerate(data["itemListElement"][:3]):
                        prod = item.get("item", {})
                        if prod and prod.get("@type") == "Product":
                            print(f"    Item {j + 1}: {prod.get('name')}")
            elif isinstance(data, list):
                print(f"  Contains a list with {len(data)} items")
                for j, item in enumerate(data[:3]):
                    if item.get("@type") == "Product":
                        print(f"    Item {j + 1}: {item.get('name')}")

        except Exception as e:
            print(f"  Error parsing JSON-LD #{i + 1}: {e}")

    return json_ld_data


def analyze_page(html_file=None, url=None, container_class=None, output_file=None):
    """
    Analyzes an HTML page to identify selectors for web scraping.

    Args:
        html_file: Path to a local HTML file
        url: URL to download HTML from
        container_class: Class name to use for product containers
        output_file: File to save the analysis results to

    Returns:
        Dictionary with analysis results

    """
    # Load HTML
    soup, base_url = load_html(html_file, url)

    # Find common elements
    common_elements = find_common_elements(soup)

    # Analyze product containers
    containers, used_container_class = analyze_product_containers(soup, container_class)

    # Suggest selectors
    suggested_selectors = suggest_selectors(containers)

    # Check for JSON-LD structured data
    json_ld_data = check_json_ld(soup)

    # Compile results
    results = {
        "common_elements": common_elements,
        "container_class": used_container_class,
        "suggested_selectors": suggested_selectors,
        "json_ld_count": len(json_ld_data),
    }

    # Save results if output_file is provided
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved analysis results to: {output_file}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Analyze HTML pages for web scraping")
    parser.add_argument(
        "--url",
        type=str,
        default="https://www.carrefour.it/spesa-online/condimenti-e-conserve/tonno-e-pesce-in-scatola/tonno-sott-olio/",
        help="URL to analyze",
    )
    parser.add_argument("--html-file", type=str, help="Use a local HTML file instead of downloading")
    parser.add_argument("--container-class", type=str, help="Class name to use for product containers")
    parser.add_argument("--save-html", type=str, help="Save the downloaded HTML to this file")
    parser.add_argument("--output-file", type=str, help="Save analysis results to this file")

    args = parser.parse_args()

    try:
        # Download the page if URL is provided and save-html is specified
        if args.url and args.save_html and not args.html_file:
            download_page(args.url, args.save_html)

        # Analyze the page
        analyze_page(
            html_file=args.html_file,
            url=None if args.html_file else args.url,
            container_class=args.container_class,
            output_file=args.output_file,
        )

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

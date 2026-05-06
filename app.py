import streamlit as st
import pandas as pd
import math
import time
from dataclasses import dataclass, field
from typing import List, Optional
from geopy.geocoders import Nominatim
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

st.set_page_config(page_title="Home Compiler", page_icon="🏡", layout="wide")

st.markdown("""
<style>
.stApp {
    background:
        linear-gradient(rgba(248, 250, 252, 0.88), rgba(248, 250, 252, 0.92)),
        url("https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1800&q=80");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}

.block-container {
    padding-top: 2rem;
    max-width: 1200px;
}

.hero {
    padding: 2rem;
    border-radius: 22px;
    background: linear-gradient(135deg, rgba(37, 99, 235, 0.95), rgba(20, 184, 166, 0.95));
    color: white;
    margin-bottom: 1.5rem;
    box-shadow: 0 14px 35px rgba(37, 99, 235, 0.25);
}

.result-card {
    padding: 1.5rem;
    border-radius: 20px;
    border: 1px solid #E2E8F0;
    background-color: rgba(255, 255, 255, 0.92);
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
    margin-bottom: 1.5rem;
}

.stButton>button {
    border-radius: 12px;
    height: 3em;
    font-weight: 700;
    background-color: #2563EB;
    color: white;
    border: none;
}

.match-strong { color: #16A34A; font-weight: 900; }
.match-good { color: #CA8A04; font-weight: 900; }
.match-weak { color: #EA580C; font-weight: 900; }
.match-poor { color: #DC2626; font-weight: 900; }
</style>
""", unsafe_allow_html=True)

geolocator = Nominatim(user_agent="home_compiler_v1")

@dataclass
class School:
    name: str
    level: str
    rating: Optional[int]
    source_url: Optional[str] = None

@dataclass
class Listing:
    address: str
    price: int
    bedrooms: int
    bathrooms: float
    square_feet: int
    has_garage: bool
    garage_spaces: int
    acres: float
    listing_url: str
    agent_name: str
    agent_contact: str
    schools: List[School] = field(default_factory=list)
    latitude: Optional[float] = None
    longitude: Optional[float] = None

@dataclass
class BuyerCriteria:
    max_price: int
    min_bedrooms: int
    min_bathrooms: float
    min_square_feet: int
    requires_garage: bool
    min_garage_spaces: int
    min_acres: float
    min_elementary_rating: int
    min_middle_rating: int
    min_high_rating: int
    reference_location: str
    max_distance_miles: float
    reference_latitude: Optional[float] = None
    reference_longitude: Optional[float] = None

def get_coordinates(location_text):
    variations = [
        location_text,
        f"{location_text}, USA",
        location_text.replace(" Ct", " Court"),
        location_text.replace(" Dr", " Drive"),
        location_text.replace(" Rd", " Road"),
        location_text.replace(" Ave", " Avenue"),
    ]

    for loc in variations:
        try:
            result = geolocator.geocode(loc, timeout=10)
            time.sleep(0.4)
            if result:
                return result.latitude, result.longitude
        except Exception:
            continue

    return None, None

def calculate_distance_miles(lat1, lon1, lat2, lon2):
    radius = 3958.8
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c

def get_best_school_by_level(schools, level):
    matching = [
        s for s in schools
        if s.level.lower() == level.lower() and s.rating is not None
    ]
    return max(matching, key=lambda s: s.rating) if matching else None

def analyze_school_fit(listing, criteria):
    targets = {
        "elementary": (get_best_school_by_level(listing.schools, "elementary"), criteria.min_elementary_rating),
        "middle": (get_best_school_by_level(listing.schools, "middle"), criteria.min_middle_rating),
        "high": (get_best_school_by_level(listing.schools, "high"), criteria.min_high_rating),
    }

    passed = []
    failed = []
    warnings = []

    for level, (school, required) in targets.items():
        if school is None:
            warnings.append(f"No {level} school rating was provided.")
            continue

        if school.rating >= required:
            passed.append(
                f"{level.title()} school meets requirement: {school.name} is {school.rating}/10, required is {required}/10."
            )
        else:
            failed.append(
                f"{level.title()} school does not meet requirement: {school.name} is {school.rating}/10, required is {required}/10."
            )

    if failed and passed:
        status = "Partial Match"
        summary = "This listing has school tradeoffs."
    elif failed:
        status = "Does Not Meet School Criteria"
        summary = "This listing does not meet the buyer's school rating preferences."
    else:
        status = "Meets School Criteria"
        summary = "This listing meets the buyer's school rating preferences."

    return {
        "overall_status": status,
        "summary": summary,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
    }

def analyze_location_fit(listing, criteria):
    if listing.latitude is None or listing.longitude is None:
        listing.latitude, listing.longitude = get_coordinates(listing.address)

    if criteria.reference_latitude is None or criteria.reference_longitude is None:
        criteria.reference_latitude, criteria.reference_longitude = get_coordinates(criteria.reference_location)

    if (
        listing.latitude is None
        or listing.longitude is None
        or criteria.reference_latitude is None
        or criteria.reference_longitude is None
    ):
        return {
            "status": "Unknown",
            "distance": None,
            "message": "Location distance could not be calculated because coordinates were unavailable."
        }

    distance = calculate_distance_miles(
        listing.latitude,
        listing.longitude,
        criteria.reference_latitude,
        criteria.reference_longitude
    )

    if distance <= criteria.max_distance_miles:
        return {
            "status": "Pass",
            "distance": distance,
            "message": f"Meets location requirement. Property is {distance:.1f} miles from {criteria.reference_location}."
        }

    return {
        "status": "Fail",
        "distance": distance,
        "message": f"Does not meet location requirement. Property is {distance:.1f} miles from {criteria.reference_location}, but buyer wants to stay within {criteria.max_distance_miles} miles."
    }

def evaluate_listing(listing, criteria):
    score = 100
    strengths = []
    concerns = []

    if listing.price <= criteria.max_price:
        strengths.append(f"Within budget at ${listing.price:,}.")
    else:
        score -= 30
        concerns.append(f"Over budget by ${listing.price - criteria.max_price:,}.")

    if listing.bedrooms >= criteria.min_bedrooms:
        strengths.append(f"Meets bedroom requirement with {listing.bedrooms} bedrooms.")
    else:
        score -= 20
        concerns.append(f"Does not meet bedroom requirement. Buyer wants {criteria.min_bedrooms}, listing has {listing.bedrooms}.")

    if listing.bathrooms >= criteria.min_bathrooms:
        strengths.append(f"Meets bathroom requirement with {listing.bathrooms} bathrooms.")
    else:
        score -= 15
        concerns.append(f"Does not meet bathroom requirement. Buyer wants {criteria.min_bathrooms}, listing has {listing.bathrooms}.")

    if listing.square_feet >= criteria.min_square_feet:
        strengths.append(f"Meets square footage requirement with {listing.square_feet:,} sq ft.")
    else:
        score -= 20
        concerns.append(f"Does not meet square footage requirement. Buyer wants {criteria.min_square_feet:,} sq ft, listing has {listing.square_feet:,} sq ft.")

    if criteria.requires_garage:
        if listing.has_garage and listing.garage_spaces >= criteria.min_garage_spaces:
            strengths.append(f"Meets garage requirement with a {listing.garage_spaces}-car garage.")
        else:
            score -= 15
            concerns.append(f"Does not meet garage requirement. Buyer wants at least a {criteria.min_garage_spaces}-car garage.")
    else:
        if listing.has_garage:
            strengths.append(f"Includes a {listing.garage_spaces}-car garage.")

    if listing.acres >= criteria.min_acres:
        strengths.append(f"Meets land requirement with {listing.acres:.2f} acres.")
    else:
        score -= 15
        concerns.append(f"Does not meet land requirement. Buyer wants at least {criteria.min_acres:.2f} acres, listing has {listing.acres:.2f} acres.")

    location = analyze_location_fit(listing, criteria)

    if location["status"] == "Pass":
        strengths.append(location["message"])
    elif location["status"] == "Fail":
        score -= 20
        concerns.append(location["message"])
    else:
        score -= 5
        concerns.append(location["message"])

    school = analyze_school_fit(listing, criteria)

    if school["overall_status"] == "Partial Match":
        score -= 15
    elif school["overall_status"] == "Does Not Meet School Criteria":
        score -= 30

    strengths.extend(school["passed"])
    concerns.extend(school["failed"])
    concerns.extend(school["warnings"])

    score = max(score, 0)

    if score >= 85:
        recommendation = "Strong Match"
    elif score >= 65:
        recommendation = "Good Match With Caveats"
    elif score >= 45:
        recommendation = "Weak Match"
    else:
        recommendation = "Poor Match"

    return {
        "Address": listing.address,
        "Fit Score": score,
        "Recommendation": recommendation,
        "Price": listing.price,
        "Beds": listing.bedrooms,
        "Baths": listing.bathrooms,
        "Sq Ft": listing.square_feet,
        "Distance": None if location["distance"] is None else round(location["distance"], 1),
        "School Status": school["overall_status"],
        "Listing URL": listing.listing_url,
        "Agent": listing.agent_name,
        "Agent Contact": listing.agent_contact,
        "Strengths": strengths,
        "Concerns": concerns,
        "Garage": "Yes" if listing.has_garage else "No",
        "Garage Spaces": listing.garage_spaces,
        "Acres": listing.acres,
    }
def create_pdf_report(results, criteria):
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Home Compiler Buyer Report", styles["Title"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph(
        f"Reference Location: {criteria.reference_location}", styles["Normal"]
    ))
    story.append(Paragraph(
        f"Maximum Distance: {criteria.max_distance_miles} miles", styles["Normal"]
    ))
    story.append(Spacer(1, 16))

    for idx, r in enumerate(results, start=1):
        story.append(Paragraph(
            f"{idx}. {r['Address']}", styles["Heading2"]
        ))

        story.append(Paragraph(
            f"Recommendation: {r['Recommendation']} ({r['Fit Score']}/100)",
            styles["Normal"]
        ))
        story.append(Paragraph(f"Price: ${r['Price']:,}", styles["Normal"]))
        story.append(Paragraph(
            f"Beds/Baths: {r['Beds']} beds, {r['Baths']} baths",
            styles["Normal"]
        ))
        story.append(Paragraph(
            f"Square Footage: {r['Sq Ft']:,} sq ft",
            styles["Normal"]
        ))

        distance_text = "Unknown" if r["Distance"] is None else f"{r['Distance']} miles"
        story.append(Paragraph(f"Distance: {distance_text}", styles["Normal"]))
        story.append(Paragraph(f"Listing URL: {r['Listing URL']}", styles["Normal"]))
        story.append(Paragraph(
            f"Agent: {r['Agent']} | {r['Agent Contact']}",
            styles["Normal"]
        ))

        story.append(Spacer(1, 8))
        story.append(Paragraph("Strengths", styles["Heading3"]))

        for item in r["Strengths"]:
            story.append(Paragraph(f"- {item}", styles["Normal"]))

        story.append(Spacer(1, 6))
        story.append(Paragraph("Concerns / Caveats", styles["Heading3"]))

        if r["Concerns"]:
            for item in r["Concerns"]:
                story.append(Paragraph(f"- {item}", styles["Normal"]))
        else:
            story.append(Paragraph("- No major concerns found.", styles["Normal"]))

        story.append(Spacer(1, 18))

    doc.build(story)
    buffer.seek(0)
    return buffer

st.markdown("""
<div class="hero">
<h1>🏡 Home Compiler</h1>
<p>A real estate listing evaluation tool that helps agents compare homes against buyer criteria, school preferences, budget, space, and location needs.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Buyer Criteria")

    max_price = st.number_input("Max Budget", min_value=0, value=500000, step=10000)
    min_bedrooms = st.number_input("Minimum Bedrooms", min_value=0, value=3, step=1)
    min_bathrooms = st.number_input("Minimum Bathrooms", min_value=0.0, value=2.0, step=0.5)
    min_square_feet = st.number_input("Minimum Square Footage", min_value=0, value=2000, step=100)
    requires_garage = st.checkbox("Requires Garage", value=False)

    min_garage_spaces = 0
    if requires_garage:
        min_garage_spaces = st.number_input(
        "Minimum Garage Spaces",
        min_value=1,
        value=2,
        step=1
    )

    min_acres = st.number_input(
    "Minimum Land Size in Acres",
    min_value=0.0,
    value=0.25,
    step=0.05,
    format="%.2f"
)

    st.subheader("School Requirements")
    min_elementary_rating = st.slider("Minimum Elementary Rating", 1, 10, 6)
    min_middle_rating = st.slider("Minimum Middle School Rating", 1, 10, 6)
    min_high_rating = st.slider("Minimum High School Rating", 1, 10, 7)

    st.subheader("Location Requirement")
    reference_location = st.text_input("Preferred Location", value="Columbia Mall, Columbia, MD")
    max_distance_miles = st.number_input("Max Distance in Miles", min_value=0.0, value=10.0, step=1.0)

criteria = BuyerCriteria(
    max_price=max_price,
    min_bedrooms=min_bedrooms,
    min_bathrooms=min_bathrooms,
    min_square_feet=min_square_feet,
    requires_garage=requires_garage,
    min_garage_spaces=min_garage_spaces,
    min_acres=min_acres,
    min_elementary_rating=min_elementary_rating,
    min_middle_rating=min_middle_rating,
    min_high_rating=min_high_rating,
    reference_location=reference_location,
    max_distance_miles=max_distance_miles
)

if "listings" not in st.session_state:
    st.session_state.listings = []

if "results" not in st.session_state:
    st.session_state.results = []

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.header("Listing Entry")
st.caption("Enter one property at a time. After adding listings, evaluate them against the buyer criteria.")

with st.form("listing_form", clear_on_submit=True):
    tab1, tab2, tab3, tab4 = st.tabs([
        "Property Details",
        "Agent Information",
        "School Ratings",
        "Property Features"
    ])

    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            address = st.text_input("Property Address")
            price = st.number_input("Price", min_value=0, value=450000, step=10000)
            bedrooms = st.number_input("Bedrooms", min_value=0, value=3, step=1)

        with col2:
            bathrooms = st.number_input("Bathrooms", min_value=0.0, value=2.0, step=0.5)
            square_feet = st.number_input("Square Footage", min_value=0, value=2000, step=100)
            listing_url = st.text_input("Listing URL")

    with tab2:
        col1, col2 = st.columns(2)

        with col1:
            agent_name = st.text_input("Agent Name")

        with col2:
            agent_contact = st.text_input("Agent Contact")

    with tab3:
        c1, c2, c3 = st.columns(3)

        with c1:
            elementary_name = st.text_input("Elementary School Name")
            elementary_rating = st.slider("Elementary Rating", 1, 10, 6)
            elementary_url = st.text_input("Elementary Source URL")

        with c2:
            middle_name = st.text_input("Middle School Name")
            middle_rating = st.slider("Middle Rating", 1, 10, 6)
            middle_url = st.text_input("Middle Source URL")

        with c3:
            high_name = st.text_input("High School Name")
            high_rating = st.slider("High School Rating", 1, 10, 7)
            high_url = st.text_input("High School Source URL")

    with tab4:
        st.subheader("Property Features")

        has_garage = st.checkbox("Has Garage?", value=True)

        garage_spaces = 0
        if has_garage:
            garage_spaces = st.number_input(
                "Garage Spaces",
                min_value=1,
                value=2,
                step=1
            )

        acres = st.number_input(
            "Land Size in Acres",
            min_value=0.0,
            value=0.25,
            step=0.05,
            format="%.2f"
        )

    submitted = st.form_submit_button("Add Listing")

if submitted:
        if not address:
            st.error("Please enter a property address.")
        else:
          listing = Listing(
    address=address,
    price=price,
    bedrooms=bedrooms,
    bathrooms=bathrooms,
    square_feet=square_feet,
    has_garage=has_garage,
    garage_spaces=garage_spaces,
    acres=acres,
    listing_url=listing_url,
    agent_name=agent_name,
    agent_contact=agent_contact,
    schools=[
        School(elementary_name or "Elementary School", "elementary", elementary_rating, elementary_url),
        School(middle_name or "Middle School", "middle", middle_rating, middle_url),
        School(high_name or "High School", "high", high_rating, high_url),
    ]
)
        st.session_state.listings.append(listing)
        st.success("Listing added successfully.")

col_a, col_b = st.columns([1, 1])

with col_a:
    if st.button("Evaluate Listings"):
        if not st.session_state.listings:
            st.warning("Add at least one listing first.")
        else:
            with st.spinner("Evaluating listings and calculating distances..."):
                results = [evaluate_listing(listing, criteria) for listing in st.session_state.listings]
                st.session_state.results = sorted(results, key=lambda x: x["Fit Score"], reverse=True)

with col_b:
    if st.button("Clear All Listings"):
        st.session_state.listings = []
        st.session_state.results = []
        st.success("All listings cleared.")

if st.session_state.listings:
    st.success(f"{len(st.session_state.listings)} listing(s) currently added.")

if st.session_state.listings:
    st.subheader("Listings Added")
    added_df = pd.DataFrame([
        {
            "Address": l.address,
            "Price": f"${l.price:,}",
            "Beds": l.bedrooms,
            "Baths": l.bathrooms,
            "Sq Ft": f"{l.square_feet:,}",
            "Agent": l.agent_name,
        }
        for l in st.session_state.listings
    ])
    st.dataframe(added_df, use_container_width=True)
    st.subheader("Edit Existing Listing")

if st.session_state.listings:
    listing_options = [
        f"{i + 1}. {listing.address}"
        for i, listing in enumerate(st.session_state.listings)
    ]

    selected = st.selectbox("Choose listing to edit", listing_options)
    selected_index = listing_options.index(selected)
    selected_listing = st.session_state.listings[selected_index]

    with st.form("edit_listing_form"):
        edited_address = st.text_input("Property Address", selected_listing.address)
        edited_price = st.number_input("Price", value=selected_listing.price, step=10000)
        edited_bedrooms = st.number_input("Bedrooms", value=selected_listing.bedrooms, step=1)
        edited_bathrooms = st.number_input("Bathrooms", value=selected_listing.bathrooms, step=0.5)
        edited_square_feet = st.number_input("Square Footage", value=selected_listing.square_feet, step=100)
        edited_listing_url = st.text_input("Listing URL", selected_listing.listing_url)
        edited_agent_name = st.text_input("Agent Name", selected_listing.agent_name)
        edited_agent_contact = st.text_input("Agent Contact", selected_listing.agent_contact)

        st.markdown("### School Ratings")

        elementary = get_best_school_by_level(selected_listing.schools, "elementary")
        middle = get_best_school_by_level(selected_listing.schools, "middle")
        high = get_best_school_by_level(selected_listing.schools, "high")

        edited_elementary_name = st.text_input(
            "Elementary School Name",
            elementary.name if elementary else ""
        )
        edited_elementary_rating = st.slider(
            "Elementary Rating",
            1, 10,
            elementary.rating if elementary and elementary.rating else 6
        )

        edited_middle_name = st.text_input(
            "Middle School Name",
            middle.name if middle else ""
        )
        edited_middle_rating = st.slider(
            "Middle Rating",
            1, 10,
            middle.rating if middle and middle.rating else 6
        )

        edited_high_name = st.text_input(
            "High School Name",
            high.name if high else ""
        )
        edited_high_rating = st.slider(
            "High School Rating",
            1, 10,
            high.rating if high and high.rating else 7
        )

        update_listing = st.form_submit_button("Update Listing")

        if update_listing:
            edited_has_garage = st.checkbox(
    "Has Garage?",
    value=selected_listing.has_garage
)

edited_garage_spaces = 0

if edited_has_garage:
    edited_garage_spaces = st.number_input(
        "Garage Spaces",
        min_value=1,
        value=selected_listing.garage_spaces if selected_listing.garage_spaces else 1,
        step=1
    )

edited_acres = st.number_input(
    "Land Size in Acres",
    min_value=0.0,
    value=float(selected_listing.acres),
    step=0.05,
    format="%.2f"
)

st.session_state.listings[selected_index] = Listing(
    address=edited_address,
    price=edited_price,
    bedrooms=edited_bedrooms,
    bathrooms=edited_bathrooms,
    square_feet=edited_square_feet,
    has_garage=edited_has_garage,
    garage_spaces=edited_garage_spaces,
    acres=edited_acres,
    listing_url=edited_listing_url,
    agent_name=edited_agent_name,
    agent_contact=edited_agent_contact,
    schools=[
        School(
            edited_elementary_name or "Elementary School",
            "elementary",
            edited_elementary_rating
        ),
        School(
            edited_middle_name or "Middle School",
            "middle",
            edited_middle_rating
        ),
        School(
            edited_high_name or "High School",
            "high",
            edited_high_rating
        ),
    ]
)
    st.session_state.results = []
    st.success("Listing updated. Click Analyze Homes again to refresh results.")
    

if st.session_state.results:
    st.header("Ranked Results Summary")

    table_rows = []
    for r in st.session_state.results:
        table_rows.append({
            "Address": r["Address"],
            "Fit Score": r["Fit Score"],
            "Recommendation": r["Recommendation"],
            "Price": f"${r['Price']:,}",
            "Beds": r["Beds"],
            "Baths": r["Baths"],
            "Sq Ft": f"{r['Sq Ft']:,}",
            "Distance": "Unknown" if r["Distance"] is None else f"{r['Distance']} miles",
            "School Status": r["School Status"],
            "Agent": r["Agent"],
            "Agent Contact": r["Agent Contact"],
            "Listing URL": r["Listing URL"],
        })

    df = pd.DataFrame(table_rows)
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Results as CSV",
        data=csv,
        file_name="home_compiler_results.csv",
        mime="text/csv"
    )
pdf_buffer = create_pdf_report(st.session_state.results, criteria)

st.download_button(
    label="📄 Download Buyer Report (PDF)",
    data=pdf_buffer,
    file_name="home_compiler_report.pdf",
    mime="application/pdf"
)
st.header("Detailed Listing Analysis")

for r in st.session_state.results:
        if r["Recommendation"] == "Strong Match":
            badge = "STRONG MATCH"
            css_class = "match-strong"
        elif r["Recommendation"] == "Good Match With Caveats":
            badge = "GOOD MATCH WITH CAVEATS"
            css_class = "match-good"
        elif r["Recommendation"] == "Weak Match":
            badge = "WEAK MATCH"
            css_class = "match-weak"
        else:
            badge = "POOR MATCH"
            css_class = "match-poor"


        st.markdown(f"""
        ### {r['Address']}
        <span class="{css_class}">{badge} ({r['Fit Score']}/100)</span>
        """, unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Price", f"${r['Price']:,}")
        c2.metric("Beds/Baths", f"{r['Beds']} / {r['Baths']}")
        c3.metric("Sq Ft", f"{r['Sq Ft']:,}")
        c4.metric("Distance", "Unknown" if r["Distance"] is None else f"{r['Distance']} mi")

        st.write(f"Listing URL: {r['Listing URL']}")
        st.write(f"Agent: {r['Agent']} | {r['Agent Contact']}")

        left, right = st.columns(2)

        with left:
            st.markdown("**Strengths**")
            for s in r["Strengths"]:
                st.write(f"- {s}")

        with right:
            st.markdown("**Concerns / Caveats**")
            if r["Concerns"]:
                for c in r["Concerns"]:
                    st.write(f"- {c}")
            else:
                st.write("- No major concerns found.")


def generate_listing(room_type, objects, details=None):
    """
    Generate a realestate.com.au style property listing.
    """
    if details is None:
        details = {}

    beds      = details.get("beds", "")
    baths     = details.get("baths", "")
    parking   = details.get("parking", "")
    land_size = details.get("land_size", "")
    suburb    = details.get("suburb", "Adelaide")
    price     = details.get("price", "")
    tone      = details.get("tone", "professional")
    prop_type = details.get("prop_type", "property")
    features  = details.get("features", "")

    # Build property summary
    parts = []
    if beds:      parts.append(f"{beds} bedroom")
    if baths:     parts.append(f"{baths} bathroom")
    if parking:   parts.append(f"{parking} car garage")
    summary = " | ".join(parts) if parts else prop_type

    # Build features string from YOLO detected objects
    detected = ", ".join(objects[:6]) if objects else "quality fixtures and fittings"

    # Add manual features from form
    extra = f" Additional highlights include {features}." if features else ""

    price_line = f"Offers invited around {price}. " if price else ""
    land_line  = f"Set on approximately {land_size}. " if land_size else ""

    if tone == "luxury":
        listing = f"""Welcome to an extraordinary residence in the prestigious suburb of {suburb}.

This distinguished {summary} {prop_type.lower()} presents an unparalleled lifestyle opportunity for the discerning buyer. Every detail has been carefully considered, from the {detected} through to the seamless indoor-outdoor flow that defines contemporary luxury living.{extra}

{land_line}Perfectly positioned in {suburb}, this home offers effortless access to the finest dining, boutique shopping, and top-rated schools the area has to offer. The architectural quality and premium finishes set this property apart from anything else currently on the market.

{price_line}Private inspections are available by appointment. Contact your agent today to experience this exceptional home firsthand."""

    elif tone == "investment":
        listing = f"""Outstanding investment opportunity now available in {suburb}!

This well-presented {summary} {prop_type.lower()} offers exceptional rental appeal and strong potential returns in one of Adelaide's most sought-after locations. The {room_type.lower()} showcases {detected}, making it highly attractive to quality tenants seeking modern, comfortable living.{extra}

{land_line}Located in {suburb} with easy access to public transport, schools, and local amenities — key drivers of sustained rental demand in this area. Currently presenting a rare chance to secure a high-performing asset in a tightly held suburb.

{price_line}Call today to discuss the investment potential of this outstanding property."""

    elif tone == "family":
        listing = f"""Welcome home to this wonderful family residence in the heart of {suburb}!

Designed with family living at its very best, this generous {summary} {prop_type.lower()} offers everything your growing family needs. The {room_type.lower()} is a standout feature, boasting {detected} and creating the perfect environment for making lasting memories.{extra}

{land_line}Situated in the family-friendly suburb of {suburb}, you will enjoy close proximity to top-rated schools, parks, sporting facilities, and all the amenities that make daily life a joy.

{price_line}Opportunities like this do not last long — arrange your inspection today!"""

    elif tone == "short":
        listing = f"""Fantastic {summary} in {suburb}!

Featuring {detected}.{extra} {land_line}{price_line}

Inspect today — this one won't last!"""

    else:
        # Professional (default)
        listing = f"""Presenting this well-appointed {summary} {prop_type.lower()} in the desirable suburb of {suburb}.

This property offers a comfortable and stylish lifestyle with a thoughtfully designed {room_type.lower()} showcasing {detected}.{extra} The practical floor plan suits a wide range of buyers, from first home buyers through to downsizers and investors alike.

{land_line}Conveniently located in {suburb} with easy access to local shops, schools, public transport, and all essential amenities.

{price_line}Contact your agent today to arrange a private inspection."""

    return listing


def generate_facebook_ads(room_type, objects, details=None):
    """
    Generate 2 Facebook/Instagram ad variations.
    """
    if details is None:
        details = {}

    suburb    = details.get("suburb", "Adelaide")
    beds      = details.get("beds", "")
    baths     = details.get("baths", "")
    price     = details.get("price", "")
    tone      = details.get("tone", "professional")
    features  = details.get("features", "")

    detected  = ", ".join(objects[:3]) if objects else "stunning features"
    bed_bath  = f"{beds}bed/{baths}bath" if beds and baths else "beautiful"
    price_txt = f"From {price}" if price else "Priced to sell"
    feat_txt  = f" Plus: {features}." if features else ""

    if tone == "luxury":
        ad1 = (f"Luxury living awaits in {suburb}. "
               f"This {bed_bath} masterpiece features {detected}.{feat_txt} "
               f"{price_txt}. Book your private inspection today.\n"
               f"#LuxuryRealEstate #{suburb}Homes #DreamHome #AdelaideProperty")

        ad2 = (f"Elevate your lifestyle in {suburb}. "
               f"A rare {bed_bath} residence crafted for those who demand the very best — "
               f"{detected} and so much more.{feat_txt} "
               f"Limited inspections. DM us now!\n"
               f"#PremiumProperty #{suburb}Living #LuxuryHomes #AdelaideRealEstate")

    elif tone == "investment":
        ad1 = (f"Smart investors are looking at {suburb} right now! "
               f"This {bed_bath} property with {detected} is perfect for your portfolio.{feat_txt} "
               f"{price_txt}. Strong rental yields in this area!\n"
               f"#InvestmentProperty #{suburb} #PropertyInvestment #AdelaideProperty")

        ad2 = (f"Don't miss this investment gem in {suburb}! "
               f"{bed_bath} with {detected}. High rental demand, great location.{feat_txt} "
               f"{price_txt}. Message us for the numbers!\n"
               f"#RealEstateInvesting #{suburb}Property #PropertyAustralia #AdelaideInvestor")

    elif tone == "family":
        ad1 = (f"Your dream family home is here in {suburb}! "
               f"Spacious {bed_bath} with {detected} — room for the whole family!{feat_txt} "
               f"{price_txt}. Inspect this weekend!\n"
               f"#FamilyHome #{suburb} #AdelaideHomes #HomeForSale")

        ad2 = (f"Make memories in {suburb}! "
               f"This gorgeous {bed_bath} family home features {detected}.{feat_txt} "
               f"Close to top schools and parks. {price_txt}.\n"
               f"#FamilyLiving #{suburb}RealEstate #AdelaideFamilyHomes #NewHome")

    else:
        ad1 = (f"Now listed in {suburb}! "
               f"This {bed_bath} property features {detected}.{feat_txt} "
               f"{price_txt}. Contact us to book an inspection today!\n"
               f"#RealEstate #{suburb} #AdelaideProperty #ForSale")

        ad2 = (f"Great opportunity in {suburb}! "
               f"Stylish {bed_bath} home with {detected}.{feat_txt} "
               f"Well located and move-in ready. {price_txt}.\n"
               f"#{suburb}Homes #AdelaideRealEstate #PropertyForSale #HomeGoals")

    return [ad1, ad2]


# Keep old function name working for backwards compatibility
def generate_description(objects, prompt, rooms):
    unique_rooms   = set(rooms)
    unique_objects = set(objects)
    return f"This property includes {', '.join(unique_rooms)} featuring {', '.join(unique_objects)}. {prompt}"

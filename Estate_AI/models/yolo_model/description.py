def generate_listing(room_type, objects, details=None):
    """
    Generate a realestate.com.au style property listing.
    Format: 2-3 descriptive paragraphs followed by a "The Highlights:" bullet list.
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

    pt = prop_type.lower()

    # Bed/bath summary
    spec_parts = []
    if beds:    spec_parts.append(f"{beds} bedroom")
    if baths:   spec_parts.append(f"{baths} bathroom")
    if parking: spec_parts.append(f"{parking} car")
    spec_str = ", ".join(spec_parts) if spec_parts else ""

    detected = ", ".join(objects[:5]) if objects else "quality fixtures and fittings"
    price_line = f"Offers invited around {price}. " if price else ""
    land_line  = f"Set on approximately {land_size}. " if land_size else ""

    # ── Body paragraphs (tone-matched) ──────────────────────────────────────
    if tone == "luxury":
        para1 = (
            f"Welcome to an extraordinary {pt} in the prestigious suburb of {suburb}, "
            f"where every detail has been curated for those who expect nothing but the finest. "
            f"From the moment you step inside, the quality of the finishes and the considered "
            f"design speak to a standard of living that is truly exceptional."
        )
        para2 = (
            f"The home unfolds across a thoughtfully planned layout, showcasing {detected} "
            f"and seamless indoor-outdoor flow that defines contemporary luxury living. "
            f"Each space has been designed to maximise light, comfort, and elegance, "
            f"creating an environment that is as beautiful as it is liveable."
        )
        para3 = (
            f"{land_line}Perfectly positioned in {suburb}, this residence offers effortless "
            f"access to the finest dining, boutique shopping, and top-rated schools. "
            f"The architectural quality and premium finishes set this property apart from "
            f"anything else currently on the market. {price_line}"
            f"Private inspections are available by appointment."
        )

    elif tone == "investment":
        para1 = (
            f"An outstanding investment opportunity awaits in {suburb} with this well-presented "
            f"{pt}, offering exceptional rental appeal and strong long-term potential. "
            f"Positioned in one of Adelaide's most sought-after locations, this property "
            f"ticks every box for the astute investor."
        )
        para2 = (
            f"The {room_type.lower()} showcases {detected}, making it highly attractive "
            f"to quality tenants seeking modern, comfortable living. "
            f"The practical layout ensures minimal vacancy and easy ongoing management, "
            f"while the quality of finishes keeps maintenance costs low."
        )
        para3 = (
            f"{land_line}Located in {suburb} with easy access to public transport, schools, "
            f"and local amenities — key drivers of sustained rental demand. "
            f"A rare chance to secure a high-performing asset in a tightly held suburb. "
            f"{price_line}Call today to discuss the investment potential."
        )

    elif tone == "family":
        para1 = (
            f"Welcome home to this wonderful {pt} nestled in the heart of {suburb}, "
            f"where space, warmth, and convenience come together for the whole family. "
            f"From the moment you arrive, the inviting atmosphere makes it clear this is "
            f"a home designed for real family life."
        )
        para2 = (
            f"Designed with family living at its very best, the home delivers generous "
            f"proportions throughout, showcasing {detected} and a layout that effortlessly "
            f"caters to busy family routines. The living zones flow naturally together, "
            f"creating spaces where memories are made every day."
        )
        para3 = (
            f"{land_line}Situated in the family-friendly suburb of {suburb}, you will enjoy "
            f"close proximity to top-rated schools, parks, sporting facilities, and all the "
            f"amenities that make daily life a joy. "
            f"{price_line}Opportunities like this do not last long — arrange your inspection today!"
        )

    elif tone == "short":
        para1 = (
            f"Fantastic {pt} now available in {suburb}! "
            f"Featuring {detected}, this home is ready to impress from the moment you arrive. "
            f"{land_line}{price_line}"
        )
        para2 = (
            f"Well located in {suburb} with easy access to schools, shops, and transport. "
            f"Inspect today — this one won't last!"
        )
        para3 = ""

    else:
        # Professional (default)
        para1 = (
            f"Presenting this well-appointed {pt} in the desirable suburb of {suburb}, "
            f"offering a comfortable and stylish lifestyle in a sought-after location. "
            f"Thoughtfully designed to maximise space and natural light, this home is "
            f"ready to welcome its next chapter."
        )
        para2 = (
            f"The {room_type.lower()} is a standout feature, showcasing {detected} and a "
            f"practical floor plan that suits a wide range of buyers — from first home buyers "
            f"through to downsizers and investors. Every room has been designed with everyday "
            f"comfort in mind, delivering a home that is both functional and appealing."
        )
        para3 = (
            f"{land_line}Conveniently located in {suburb} with easy access to local shops, "
            f"schools, public transport, and all essential amenities. "
            f"{price_line}Contact your agent today to arrange a private inspection."
        )

    # ── Highlight bullets ────────────────────────────────────────────────────
    bullets = []

    # Property type
    if spec_str:
        bullets.append(f"{spec_str.capitalize()} {pt}")
    else:
        bullets.append(f"{prop_type} in {suburb}")

    # Bedrooms
    if beds:
        bullets.append(f"{beds} {'bedroom' if beds == '1' else 'bedrooms'} with built-in robes")

    # Bathrooms
    if baths:
        bullets.append(f"{baths} {'bathroom' if baths == '1' else 'bathrooms'} with quality fittings")

    # Detected objects → feature bullets
    obj_map = {
        "couch":        "Spacious open-plan living area",
        "sofa":         "Spacious open-plan living area",
        "dining table": "Dedicated dining area",
        "oven":         "Modern kitchen with quality appliances",
        "microwave":    "Modern kitchen with quality appliances",
        "refrigerator": "Well-appointed kitchen",
        "sink":         "Well-appointed kitchen",
        "bed":          "Comfortable bedroom accommodation",
        "toilet":       "Multiple bathrooms and toilets for convenience",
        "potted plant": "Landscaped outdoor surrounds",
        "car":          "Secure off-street parking",
        "tv":           "Entertainment-ready living space",
        "chair":        "Stylishly presented interiors",
    }
    seen_bullets = set(bullets)
    for obj in objects[:6]:
        phrase = obj_map.get(obj.lower())
        if phrase and phrase not in seen_bullets:
            bullets.append(phrase)
            seen_bullets.add(phrase)

    # Parking
    if parking:
        park_bullet = f"{'Secure' if int(parking) > 1 else 'Dedicated'} {parking}-car parking"
        if park_bullet not in seen_bullets:
            bullets.append(park_bullet)

    # Land size
    if land_size:
        bullets.append(f"Generous {land_size} allotment")

    # Extra features from form
    if features:
        for feat in features.split(","):
            f = feat.strip()
            if f and f not in seen_bullets:
                bullets.append(f)
                seen_bullets.add(f)

    # Tone-specific closing bullet
    tone_bullets = {
        "luxury":     "Premium finishes and fixtures throughout",
        "investment": "Ideal for investors — strong rental appeal",
        "family":     "Close to schools, parks, and family amenities",
        "short":      "Move-in ready condition",
        "professional": f"Sought-after location in {suburb}",
    }
    closing = tone_bullets.get(tone, f"Sought-after location in {suburb}")
    if closing not in seen_bullets:
        bullets.append(closing)

    highlights = "The Highlights:\n" + "\n".join(f"- {b}" for b in bullets)

    # ── Assemble final listing ───────────────────────────────────────────────
    paras = [p for p in [para1, para2, para3] if p]
    listing = "\n\n".join(paras) + "\n\n" + highlights

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

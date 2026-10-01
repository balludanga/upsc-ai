"""Clearly labeled, non-PYQ questions for testing the Prelims practice UI."""

from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.models import PrelimsQuestion, PrelimsQuestionLevel


DEMO_SOURCE = "Demo mock question — not an official UPSC PYQ"
DEMO_SOURCE_ID = hashlib.sha256(b"upsc-prelims-demo-bank-v1").hexdigest()
_LETTERS = ("A", "B", "C", "D")

# subject, topic, question, options, answer, explanation
_QUESTIONS = [
    # Indian Polity
    ("Indian Polity", "Constitution", "Which Article guarantees equality before the law?", ("Article 14", "Article 19", "Article 21", "Article 32"), "A", "Article 14 guarantees equality before the law and equal protection of the laws."),
    ("Indian Polity", "Constitution", "The protection of life and personal liberty is provided by which Article?", ("Article 15", "Article 17", "Article 21", "Article 25"), "C", "Article 21 protects life and personal liberty."),
    ("Indian Polity", "Parliament", "Who decides whether a Bill is a Money Bill in the Lok Sabha?", ("The President", "The Speaker", "The Finance Minister", "The Chairman of the Rajya Sabha"), "B", "The Speaker of the Lok Sabha certifies a Bill as a Money Bill."),
    ("Indian Polity", "Parliament", "Which statement about the Rajya Sabha is correct?", ("It is dissolved every five years.", "It is a permanent House, with one-third of its members retiring every two years.", "It can have no more than 100 members.", "It is chaired by the President."), "B", "The Rajya Sabha is not subject to dissolution; approximately one-third of its members retire every two years."),
    ("Indian Polity", "Elections", "Which group participates in the election of the President of India?", ("All citizens aged 18 and above", "Elected MPs and elected members of State Legislative Assemblies", "Only members of the Lok Sabha", "Elected MPs and all members of State Legislative Councils"), "B", "The electoral college includes elected MPs and elected MLAs of States and specified Union Territories."),
    ("Indian Polity", "Constitution", "The Directive Principles of State Policy are contained in which Part of the Constitution?", ("Part II", "Part III", "Part IV", "Part IVA"), "C", "Directive Principles are set out in Part IV."),
    ("Indian Polity", "Local Government", "Which Constitutional Amendment gave constitutional status to Panchayati Raj institutions?", ("42nd Amendment", "44th Amendment", "73rd Amendment", "74th Amendment"), "C", "The 73rd Amendment concerns Panchayats."),
    ("Indian Polity", "Local Government", "Which Constitutional Amendment concerns municipalities?", ("52nd Amendment", "61st Amendment", "73rd Amendment", "74th Amendment"), "D", "The 74th Amendment concerns urban local bodies, including municipalities."),
    ("Indian Polity", "Constitutional Bodies", "The Finance Commission is constituted under which Article?", ("Article 148", "Article 280", "Article 324", "Article 356"), "B", "Article 280 provides for a Finance Commission."),
    ("Indian Polity", "Constitutional Bodies", "Which Article provides for the Comptroller and Auditor General of India?", ("Article 76", "Article 148", "Article 280", "Article 368"), "B", "The office of the CAG is provided for in Article 148."),
    # History
    ("History", "Ancient India", "Which ancient Indian site is especially associated with a large public water tank known as the Great Bath?", ("Harappa", "Mohenjo-daro", "Kalibangan", "Rakhigarhi"), "B", "The Great Bath is a well-known structure at Mohenjo-daro."),
    ("History", "Ancient India", "Which Harappan site is associated with a large basin often interpreted as a water-management structure?", ("Dholavira", "Taxila", "Sarnath", "Pataliputra"), "A", "Dholavira is noted for reservoirs and sophisticated water management."),
    ("History", "Ancient India", "The script used by the Harappan civilisation is best described as:", ("Fully deciphered and alphabetic", "Undeciphered", "Written only in Sanskrit", "A form of Brahmi"), "B", "The Indus script has not been conclusively deciphered."),
    ("History", "Buddhism", "Where did the Buddha deliver his first sermon?", ("Bodh Gaya", "Sarnath", "Lumbini", "Kushinagar"), "B", "The first sermon is traditionally associated with Sarnath."),
    ("History", "Buddhism", "The Buddha's Mahaparinirvana is traditionally associated with which place?", ("Vaishali", "Rajgir", "Kushinagar", "Sanchi"), "C", "Kushinagar is traditionally identified as the place of the Buddha's Mahaparinirvana."),
    ("History", "Mauryan Empire", "Which ruler is credited with founding the Mauryan Empire?", ("Ashoka", "Chandragupta Maurya", "Bindusara", "Kanishka"), "B", "Chandragupta Maurya established the Mauryan Empire."),
    ("History", "Mauryan Empire", "Which Greek ambassador's account, known as the Indica, describes the Mauryan period?", ("Megasthenes", "Fa-Hien", "Hiuen Tsang", "Pliny"), "A", "Megasthenes served at the Mauryan court and wrote the Indica."),
    ("History", "Mauryan Empire", "Which war is widely associated with Emperor Ashoka's turn toward Dhamma?", ("Battle of Hydaspes", "Kalinga War", "Battle of Tarain", "Battle of Panipat"), "B", "Ashoka's remorse after the Kalinga War is described in his inscriptions."),
    ("History", "Ancient India", "Which mathematician and astronomer authored the Aryabhatiya?", ("Varahamihira", "Brahmagupta", "Aryabhata", "Bhaskara II"), "C", "Aryabhata composed the Aryabhatiya."),
    ("History", "National Movement", "The Quit India Movement was launched in which year?", ("1919", "1930", "1942", "1946"), "C", "The Quit India Movement began in August 1942."),
    # Geography
    ("Geography", "Indian Rivers", "Which major peninsular river flows westward into the Arabian Sea?", ("Godavari", "Krishna", "Narmada", "Mahanadi"), "C", "The Narmada flows west through a rift valley to the Arabian Sea."),
    ("Geography", "Indian Rivers", "Which is the longest river that flows entirely within India?", ("Godavari", "Ganga", "Brahmaputra", "Indus"), "A", "The Godavari is the longest river flowing entirely within India."),
    ("Geography", "Indian Climate", "How many Indian states does the Tropic of Cancer pass through?", ("Six", "Seven", "Eight", "Nine"), "C", "The Tropic of Cancer passes through eight Indian states."),
    ("Geography", "Soils", "Black soil is particularly suitable for which crop?", ("Tea", "Cotton", "Jute", "Coffee"), "B", "Black soil retains moisture and is well suited to cotton cultivation."),
    ("Geography", "Physical Geography", "Which mountain range along India's western coast is relatively continuous?", ("Aravalli Range", "Western Ghats", "Vindhya Range", "Satpura Range"), "B", "The Western Ghats form a comparatively continuous escarpment along the western side of the peninsula."),
    ("Geography", "Indian Lakes", "Chilika Lake is located in which state?", ("Andhra Pradesh", "Odisha", "West Bengal", "Kerala"), "B", "Chilika is a brackish-water lagoon on the Odisha coast."),
    ("Geography", "Physical Geography", "The Sundarbans delta is primarily formed by which river system?", ("Narmada and Tapi", "Godavari and Krishna", "Ganga and Brahmaputra", "Mahanadi and Subarnarekha"), "C", "The Ganga-Brahmaputra river system forms the Sundarbans delta."),
    ("Geography", "Indian Climate", "The seasonal reversal of winds over the Indian subcontinent is most closely associated with:", ("The monsoon", "The polar easterlies", "The land breeze alone", "The westerlies throughout the year"), "A", "The monsoon is characterised by a seasonal reversal of winds."),
    ("Geography", "Physical Geography", "The Aravalli Range is generally classified as:", ("A young fold mountain range", "An ancient residual mountain range", "A volcanic island arc", "A coastal range formed by coral growth"), "B", "The Aravallis are among the world's ancient mountain systems and are heavily eroded."),
    ("Geography", "Indian Agriculture", "Which soil type is commonly found across much of the northern Indo-Gangetic plain?", ("Alluvial soil", "Laterite soil", "Black soil", "Peaty soil"), "A", "Alluvial deposits cover extensive areas of the Indo-Gangetic plain."),
    # Economy
    ("Indian Economy", "Banking", "In which year did the Reserve Bank of India begin operations?", ("1921", "1935", "1947", "1950"), "B", "The RBI began operations on 1 April 1935."),
    ("Indian Economy", "Monetary Policy", "In India, the repo rate is the rate at which:", ("Banks lend to their customers", "The RBI lends short-term funds to banks against eligible securities", "The government lends to the RBI", "Banks lend to one another without collateral"), "B", "The repo rate is the rate at which the RBI lends to banks under the repo facility."),
    ("Indian Economy", "Monetary Policy", "Under the Cash Reserve Ratio requirement, scheduled banks keep a prescribed share of deposits as cash with:", ("The Reserve Bank of India", "NITI Aayog", "The Ministry of Finance", "The Securities and Exchange Board of India"), "A", "Banks maintain CRR balances with the RBI."),
    ("Indian Economy", "National Income", "Gross Domestic Product measures the value of final goods and services produced:", ("By citizens anywhere in the world", "Within a country's domestic territory during a period", "Only by government enterprises", "Only for export"), "B", "GDP measures final production within domestic territory over a specified period."),
    ("Indian Economy", "Prices and Inflation", "Inflation refers to:", ("A sustained rise in the general price level", "A fall in all wages", "A rise in the value of money", "A fall in total production alone"), "A", "Inflation is a sustained increase in the general level of prices."),
    ("Indian Economy", "Public Finance", "Fiscal deficit is broadly the gap between total expenditure and:", ("Total receipts excluding borrowings", "Tax revenue alone", "Exports and imports", "Revenue expenditure and capital expenditure"), "A", "Fiscal deficit is total expenditure minus receipts excluding borrowings."),
    ("Indian Economy", "Taxation", "The Goods and Services Tax is primarily a:", ("Direct tax on income", "Destination-based indirect tax on supply", "Tax on agricultural land only", "Tax collected only by local bodies"), "B", "GST is a destination-based indirect tax on the supply of goods and services."),
    ("Indian Economy", "Institutions", "Which institution replaced the Planning Commission in 2015?", ("Finance Commission", "NITI Aayog", "National Development Council", "Reserve Bank of India"), "B", "NITI Aayog was established in 2015 to replace the Planning Commission."),
    ("Indian Economy", "Financial Markets", "Which institution regulates the securities market in India?", ("SEBI", "IRDAI", "NABARD", "CAG"), "A", "The Securities and Exchange Board of India regulates the securities market."),
    ("Indian Economy", "Monetary Policy", "Which body sets India's benchmark policy interest rate through monetary policy decisions?", ("Monetary Policy Committee", "GST Council", "Finance Commission", "Election Commission"), "A", "The RBI's Monetary Policy Committee determines the policy repo rate."),
    # Environment
    ("Environment", "Ecology", "In a food chain, green plants are generally classified as:", ("Primary producers", "Secondary consumers", "Decomposers", "Scavengers"), "A", "Green plants produce organic matter using sunlight and form the base of most food chains."),
    ("Environment", "Biodiversity", "The IUCN Red List primarily assesses:", ("The conservation status of species", "The quality of drinking water", "National greenhouse-gas inventories", "The boundaries of wetlands"), "A", "The IUCN Red List evaluates the extinction risk and conservation status of species."),
    ("Environment", "Wetlands", "The Ramsar Convention is principally concerned with the conservation of:", ("Wetlands", "Deserts", "Mountain glaciers", "Coral-mining sites"), "A", "The Ramsar Convention provides an international framework for wetland conservation."),
    ("Environment", "Wildlife", "CITES is an international agreement focused on:", ("Trade in endangered wild animals and plants", "Control of marine plastic only", "Protection of cultural heritage", "Management of nuclear materials"), "A", "CITES regulates international trade in listed wild fauna and flora."),
    ("Environment", "Ozone Layer", "The Montreal Protocol is best known for controlling substances that deplete the:", ("Ozone layer", "Lithosphere", "Tropospheric oxygen", "Ocean salinity"), "A", "The Montreal Protocol phases out ozone-depleting substances."),
    ("Environment", "Climate Change", "The Kyoto Protocol established commitments primarily related to:", ("Greenhouse-gas emissions", "International whaling", "Wetland listing", "Trade in hazardous waste"), "A", "The Kyoto Protocol set emission-reduction commitments for participating developed countries."),
    ("Environment", "Ecosystems", "Mangrove plants are specially adapted to grow in:", ("Saline coastal and intertidal environments", "Permanently frozen tundra", "Deep open-ocean water", "Only high-altitude grasslands"), "A", "Mangroves tolerate saline, waterlogged conditions in tropical and subtropical coastal zones."),
    ("Environment", "Biodiversity", "A biodiversity hotspot is identified using high endemism and:", ("Significant habitat loss", "High annual snowfall", "Low human population alone", "A large number of deserts"), "A", "Hotspots combine high levels of endemic plants with substantial loss of original habitat."),
    ("Environment", "Ecology", "Which group commonly converts atmospheric nitrogen into forms usable by plants?", ("Certain bacteria", "Reptiles", "Mosses only", "Viruses"), "A", "Nitrogen-fixing bacteria convert atmospheric nitrogen into biologically usable compounds."),
    ("Environment", "Pollution", "Which gas is a major contributor to human-caused global warming?", ("Carbon dioxide", "Helium", "Neon", "Argon"), "A", "Carbon dioxide is a long-lived greenhouse gas emitted in large quantities by human activities."),
    # Science and Technology
    ("Science and Technology", "Physics", "What is the SI unit of force?", ("Joule", "Newton", "Watt", "Pascal"), "B", "The newton is the SI unit of force."),
    ("Science and Technology", "Human Biology", "A deficiency of vitamin C can cause:", ("Scurvy", "Rickets", "Beriberi", "Night blindness"), "A", "Vitamin C deficiency causes scurvy."),
    ("Science and Technology", "Genetics", "Which molecule carries hereditary information in most living organisms?", ("DNA", "Cellulose", "Starch", "Chlorophyll"), "A", "DNA stores genetic information in most organisms."),
    ("Science and Technology", "Astronomy", "Which planet is commonly called the Red Planet?", ("Venus", "Mars", "Jupiter", "Mercury"), "B", "Iron-rich dust gives Mars its familiar reddish appearance."),
    ("Science and Technology", "Indian Space Programme", "In which year was the Indian Space Research Organisation established?", ("1962", "1969", "1975", "1984"), "B", "ISRO was established in 1969."),
    ("Science and Technology", "Physics", "Why can sound not travel through a perfect vacuum?", ("It needs a material medium for its mechanical wave to propagate.", "Its frequency becomes zero in space.", "Vacuum absorbs every sound wave.", "Sound travels only through liquids."), "A", "Sound is a mechanical wave and requires particles in a medium to transmit vibrations."),
    ("Science and Technology", "Chemistry", "At approximately 25°C, a neutral aqueous solution has a pH close to:", ("1", "5", "7", "14"), "C", "At about 25°C, neutral water has a pH of approximately 7."),
    ("Science and Technology", "Human Biology", "Which hormone helps regulate blood glucose by promoting its uptake by cells?", ("Insulin", "Adrenaline", "Melatonin", "Thyroxine"), "A", "Insulin, produced by pancreatic beta cells, helps regulate blood glucose."),
    ("Science and Technology", "Physics", "Which subatomic particle carries a negative electric charge?", ("Proton", "Neutron", "Electron", "Alpha particle"), "C", "An electron carries a negative elementary electric charge."),
    ("Science and Technology", "Indian Space Programme", "Which Indian mission made a successful soft landing near the Moon's south polar region in 2023?", ("Mangalyaan", "Chandrayaan-2 orbiter", "Chandrayaan-3", "AstroSat"), "C", "Chandrayaan-3's lander achieved a soft landing on the Moon on 23 August 2023."),
    # Art and Culture
    ("Art and Culture", "Classical Dance", "Bharatanatyam is traditionally associated with which state?", ("Tamil Nadu", "Assam", "Punjab", "Himachal Pradesh"), "A", "Bharatanatyam developed in Tamil Nadu."),
    ("Art and Culture", "Classical Dance", "Kathak is a classical dance tradition historically associated with:", ("North India", "Kerala alone", "The Andaman Islands", "Nagaland"), "A", "Kathak developed in North India, with important regional gharanas."),
    ("Art and Culture", "Classical Dance", "Kathakali is traditionally associated with:", ("Kerala", "Odisha", "Gujarat", "Manipur"), "A", "Kathakali is a dance-drama tradition of Kerala."),
    ("Art and Culture", "Classical Dance", "Kuchipudi takes its name from a village in which state?", ("Andhra Pradesh", "Maharashtra", "Sikkim", "Haryana"), "A", "Kuchipudi is named after a village in Andhra Pradesh."),
    ("Art and Culture", "Classical Dance", "Sattriya originated in which state?", ("Assam", "Rajasthan", "Goa", "Bihar"), "A", "Sattriya developed in Assam's Vaishnavite monasteries, or sattras."),
    ("Art and Culture", "Classical Dance", "Odissi is a classical dance form associated with:", ("Odisha", "Karnataka", "Uttar Pradesh", "Meghalaya"), "A", "Odissi originated in Odisha."),
    ("Art and Culture", "Festivals", "Bihu is a major festival tradition of:", ("Assam", "Tamil Nadu", "Ladakh", "Mizoram"), "A", "Bihu festivals are central to Assamese cultural life."),
    ("Art and Culture", "Architecture", "The Ajanta caves are especially renowned for their ancient:", ("Buddhist paintings and sculptures", "Chola bronze workshops", "Mughal miniature gardens", "Rock-cut Jain temples alone"), "A", "Ajanta is noted for Buddhist cave architecture, paintings and sculpture."),
    ("Art and Culture", "Architecture", "The Great Stupa at Sanchi is located in which state?", ("Madhya Pradesh", "Kerala", "Tripura", "Himachal Pradesh"), "A", "Sanchi is in Madhya Pradesh."),
    ("Art and Culture", "Architecture", "The Sun Temple at Konark is located in:", ("Odisha", "Rajasthan", "Telangana", "Uttarakhand"), "A", "The Konark Sun Temple is on the coast of Odisha."),
    # Agriculture
    ("Agriculture", "Cropping Seasons", "Kharif crops are generally sown with the onset of the:", ("Southwest monsoon", "Winter frost", "Retreating northeast monsoon only", "Spring snowmelt"), "A", "Kharif crops are sown around the onset of the southwest monsoon."),
    ("Agriculture", "Cropping Seasons", "Rabi crops are generally sown during:", ("The winter season", "The peak southwest monsoon", "Late summer only", "The cyclone season"), "A", "Rabi crops are sown in winter and harvested in spring."),
    ("Agriculture", "Cropping Seasons", "The short cropping season between the Rabi and Kharif seasons is often called:", ("Zaid", "Boro", "Jhum", "Barani"), "A", "Zaid is a short summer cropping season between Rabi and Kharif."),
    ("Agriculture", "Crops", "Which of the following is generally a Rabi crop in India?", ("Wheat", "Cotton", "Kharif rice", "Jute"), "A", "Wheat is commonly grown as a Rabi crop."),
    ("Agriculture", "Crops", "Which crop is commonly grown during the Kharif season in much of India?", ("Rice", "Gram", "Mustard", "Pea"), "A", "Rice is a major Kharif crop, although seasons vary by region and variety."),
    ("Agriculture", "Agricultural Policy", "In India, the Commission for Agricultural Costs and Prices primarily:", ("Recommends Minimum Support Prices", "Sets the RBI policy rate", "Regulates fertiliser imports alone", "Conducts the population census"), "A", "The CACP recommends MSPs for consideration by the government."),
    ("Agriculture", "Irrigation", "Which irrigation method delivers water close to plant roots through emitters?", ("Drip irrigation", "Flood irrigation", "Furrow irrigation only", "Canal seepage"), "A", "Drip irrigation supplies water in controlled amounts near the root zone."),
    ("Agriculture", "Soil Fertility", "Which group of crops commonly forms a beneficial nitrogen-fixing association with bacteria?", ("Legumes", "Citrus fruits", "Root vegetables only", "Sugarcane"), "A", "Many legumes host nitrogen-fixing bacteria in root nodules."),
    ("Agriculture", "Soils", "Which soil is widely distributed across the Indo-Gangetic plains?", ("Alluvial soil", "Black cotton soil only", "Laterite soil", "Desert saline soil"), "A", "Alluvial soils are extensive in the Indo-Gangetic plains."),
    ("Agriculture", "Crops", "Which group includes hardy millets often suited to relatively dry conditions?", ("Pearl millet and sorghum", "Tea and coffee", "Jute and sugarcane", "Rubber and cocoa"), "A", "Pearl millet and sorghum are drought-tolerant cereals compared with many water-intensive crops."),
    # International Relations
    ("International Relations", "United Nations", "Where is the headquarters of the United Nations located?", ("New York", "Geneva", "Paris", "Vienna"), "A", "The UN headquarters is in New York City."),
    ("International Relations", "United Nations Agencies", "The headquarters of the World Health Organization is in:", ("Geneva", "Rome", "Nairobi", "The Hague"), "A", "WHO is headquartered in Geneva, Switzerland."),
    ("International Relations", "United Nations Agencies", "UNESCO is headquartered in which city?", ("Paris", "New York", "Bangkok", "Addis Ababa"), "A", "UNESCO is headquartered in Paris."),
    ("International Relations", "International Finance", "The headquarters of the International Monetary Fund is in:", ("Washington, D.C.", "Geneva", "London", "Brussels"), "A", "The IMF is headquartered in Washington, D.C."),
    ("International Relations", "Regional Organisations", "The ASEAN Secretariat is based in:", ("Jakarta", "Kathmandu", "Dhaka", "Colombo"), "A", "The ASEAN Secretariat is located in Jakarta, Indonesia."),
    ("International Relations", "Regional Organisations", "The SAARC Secretariat is located in:", ("Kathmandu", "New Delhi", "Islamabad", "Thimphu"), "A", "The SAARC Secretariat is in Kathmandu, Nepal."),
    ("International Relations", "Trade", "The World Trade Organization is headquartered in:", ("Geneva", "Vienna", "New York", "Tokyo"), "A", "The WTO is headquartered in Geneva."),
    ("International Relations", "International Law", "The International Court of Justice sits in:", ("The Hague", "Geneva", "Rome", "New York"), "A", "The ICJ is based at the Peace Palace in The Hague."),
    ("International Relations", "United Nations", "Which of these is a permanent member of the UN Security Council?", ("Brazil", "India", "China", "Japan"), "C", "China is one of the five permanent members of the Security Council."),
    ("International Relations", "International Organisations", "OPEC is headquartered in:", ("Vienna", "Riyadh", "Doha", "Geneva"), "A", "The OPEC Secretariat is in Vienna, Austria."),
    # General Science and Environment
    ("General Studies", "Science", "Which process allows green plants to convert light energy into chemical energy?", ("Photosynthesis", "Fermentation", "Combustion", "Condensation"), "A", "Photosynthesis converts light energy into chemical energy stored in organic compounds."),
    ("General Studies", "Science", "Which blood cells are primarily responsible for transporting oxygen?", ("Red blood cells", "Platelets", "White blood cells", "Lymphocytes only"), "A", "Red blood cells contain haemoglobin, which transports oxygen."),
    ("General Studies", "Science", "Which organ filters blood and produces urine?", ("Kidney", "Lung", "Pancreas", "Spleen"), "A", "The kidneys filter blood and produce urine."),
    ("General Studies", "Science", "Which vitamin is produced in human skin when exposed to suitable sunlight?", ("Vitamin A", "Vitamin C", "Vitamin D", "Vitamin K"), "C", "Ultraviolet B exposure enables the skin to synthesise vitamin D."),
    ("General Studies", "Environment", "Which of these is a renewable source of energy?", ("Solar energy", "Coal", "Petroleum", "Natural gas"), "A", "Solar energy is naturally replenished on a human timescale."),
    ("General Studies", "Environment", "Which device converts sunlight directly into electricity using photovoltaic cells?", ("Solar panel", "Diesel generator", "Steam turbine", "Electrolyser"), "A", "Photovoltaic cells in solar panels convert light directly into electricity."),
    ("General Studies", "Science", "At standard atmospheric pressure, pure water boils at approximately:", ("0°C", "50°C", "100°C", "150°C"), "C", "Pure water boils at approximately 100°C at one atmosphere of pressure."),
    ("General Studies", "Science", "Which instrument is used to measure atmospheric pressure?", ("Barometer", "Hygrometer", "Anemometer", "Seismograph"), "A", "A barometer measures atmospheric pressure."),
    ("General Studies", "Environment", "Which gas do plants absorb from the atmosphere during photosynthesis?", ("Carbon dioxide", "Oxygen", "Hydrogen", "Helium"), "A", "Plants use atmospheric carbon dioxide as a carbon source during photosynthesis."),
    ("General Studies", "Science", "Which part of a typical plant cell contains chlorophyll?", ("Chloroplast", "Ribosome", "Nucleus", "Mitochondrion"), "A", "Chlorophyll is located in chloroplasts, where photosynthesis takes place."),
]


def seed_demo_questions(db: Session) -> dict[str, int]:
    """Insert missing demo rows without changing official or existing rows."""
    existing_numbers = {
        number
        for (number,) in db.query(PrelimsQuestion.question_number)
        .filter(PrelimsQuestion.source_id == DEMO_SOURCE_ID)
        .all()
    }
    inserted = 0

    try:
        for number, item in enumerate(_QUESTIONS, start=1):
            if number in existing_numbers:
                continue

            subject, topic, question, options, answer, explanation = item
            record = PrelimsQuestion(
                source_id=DEMO_SOURCE_ID,
                question_number=number,
                year=2026,
                paper="Demo GS Paper I",
                subject=subject,
                topic=topic,
                question=question,
                options=list(options),
                correct_option=answer,
                explanation=explanation,
                source=DEMO_SOURCE,
                source_url=None,
            )
            db.add(record)
            db.flush()
            db.add(PrelimsQuestionLevel(
                question_id=record.id,
                difficulty=2 if number % 3 else 1,
            ))
            inserted += 1

        db.commit()
    except Exception:
        db.rollback()
        raise

    total = (
        db.query(PrelimsQuestion.id)
        .filter(PrelimsQuestion.source_id == DEMO_SOURCE_ID)
        .count()
    )
    return {"inserted": inserted, "total": total}


if len(_QUESTIONS) != 100:
    raise RuntimeError(f"The demo bank needs 100 questions, found {len(_QUESTIONS)}.")

if any(answer not in _LETTERS or len(options) != 4 for _, _, _, options, answer, _ in _QUESTIONS):
    raise RuntimeError("Each demo question must have four options and a valid answer.")

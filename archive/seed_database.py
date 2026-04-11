"""Seed the RPM database with 25 collector cars."""

import sys
sys.path.insert(0, '.')
from backend.database import get_db, create_tables


CARS = [
    # --- 15 specified cars ---
    {
        "year": 1967, "make": "Shelby", "model": "GT500", "trim": "Fastback",
        "price": 189000, "mileage": 43200,
        "exterior_color": "Nightmist Blue", "interior_color": "Black Vinyl",
        "engine": "427 V8", "transmission": "4-Speed Manual",
        "vin": "67402F8A00321", "status": "available", "condition": "excellent",
        "description": "A stunning first-year GT500 with the correct 427 Police Interceptor V8 and factory 4-speed. Beautifully restored in its original Nightmist Blue over black interior with full Marti Report documentation.",
        "highlights": '["matching numbers", "Marti Report documented", "frame-off restoration", "original 427 Police Interceptor engine"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/1.jpg",
        "date_listed": "2025-11-15", "views": 2847,
    },
    {
        "year": 1969, "make": "Chevrolet", "model": "Camaro", "trim": "Z/28",
        "price": 125000, "mileage": 67800,
        "exterior_color": "Hugger Orange", "interior_color": "Black Houndstooth",
        "engine": "302 V8 DZ302", "transmission": "4-Speed Muncie M21",
        "vin": "124379N507821", "status": "available", "condition": "excellent",
        "description": "Real-deal Z/28 with the screaming DZ302 small block and close-ratio Muncie. Hugger Orange with the houndstooth interior — this is the combination everyone wants. Runs and drives beautifully.",
        "highlights": '["numbers matching DZ302", "houndstooth interior", "original Protect-O-Plate", "Norwood-built"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/2.jpg",
        "date_listed": "2025-10-22", "views": 1923,
    },
    {
        "year": 1970, "make": "Plymouth", "model": "Barracuda", "trim": "'Cuda 440-6",
        "price": 275000, "mileage": 31400,
        "exterior_color": "Limelight Green", "interior_color": "Black Leather",
        "engine": "440 Six Pack V8", "transmission": "4-Speed Pistol Grip",
        "vin": "BS23V0B123456", "status": "available", "condition": "concours",
        "description": "E-body royalty. This 'Cuda wears its factory Limelight Green with the 440 Six Pack and pistol-grip four-speed. Concours-quality rotisserie restoration with fender tag and broadcast sheet.",
        "highlights": '["440 Six Pack", "pistol-grip 4-speed", "broadcast sheet", "concours rotisserie restoration", "fender tag decoded"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/3.jpg",
        "date_listed": "2025-09-05", "views": 4312,
    },
    {
        "year": 1963, "make": "Chevrolet", "model": "Corvette", "trim": "Split-Window Coupe",
        "price": 165000, "mileage": 78200,
        "exterior_color": "Riverside Red", "interior_color": "Red Vinyl",
        "engine": "327 V8 340hp", "transmission": "4-Speed Manual",
        "vin": "30837S109483", "status": "available", "condition": "excellent",
        "description": "The one-year-only split-window that defines C2 Corvettes. Factory 327/340 with 4-speed in stunning Riverside Red. Older restoration that still presents extremely well.",
        "highlights": '["one-year-only split window", "327/340hp", "4-speed manual", "NCRS Top Flight candidate"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/4.jpg",
        "date_listed": "2025-12-01", "views": 3456,
    },
    {
        "year": 1973, "make": "Porsche", "model": "911", "trim": "Carrera RS 2.7",
        "price": 1250000, "mileage": 58900,
        "exterior_color": "Grand Prix White", "interior_color": "Black Leatherette",
        "engine": "Flat-6 2.7L", "transmission": "5-Speed Manual 915",
        "vin": "9113601042", "status": "available", "condition": "excellent",
        "description": "Lightweight RS in the iconic Grand Prix White with blue script. Matching-numbers 2.7L flat-six with mechanical fuel injection. One of roughly 1,580 produced — fully documented ownership history back to new.",
        "highlights": '["matching numbers", "Lightweight spec", "documented ownership history", "COA from Porsche", "original MFI engine"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/5.jpg",
        "date_listed": "2025-08-18", "views": 4987,
    },
    {
        "year": 1971, "make": "Lamborghini", "model": "Miura", "trim": "SV",
        "price": 2800000, "mileage": 22100,
        "exterior_color": "Arancio Miura", "interior_color": "Nero Leather",
        "engine": "V12 3.9L", "transmission": "5-Speed Manual",
        "vin": "4846", "status": "available", "condition": "concours",
        "description": "The final evolution of the car that started the supercar era. This SV is one of just 150 built and wears its original Arancio Miura over black leather. Fully certified by Lamborghini Polo Storico with matching numbers throughout.",
        "highlights": '["Polo Storico certified", "matching numbers", "1 of 150 SVs", "Pebble Beach class winner", "original colors"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/6.jpg",
        "date_listed": "2025-07-10", "views": 3211,
    },
    {
        "year": 1955, "make": "Mercedes-Benz", "model": "300SL", "trim": "Gullwing",
        "price": 1450000, "mileage": 41600,
        "exterior_color": "Silver Metallic", "interior_color": "Red Leather",
        "engine": "Inline-6 3.0L Fuel Injected", "transmission": "4-Speed Manual",
        "vin": "1980405500182", "status": "pending", "condition": "concours",
        "description": "The car that put Mercedes-Benz on the sports car map. Gorgeous silver over red leather with the Bosch mechanical fuel injection inline-six. Complete with fitted luggage, tool kit, and extensive service records.",
        "highlights": '["matching numbers", "fitted luggage set", "Bosch mechanical fuel injection", "extensive service history", "original tool kit"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/7.jpg",
        "date_listed": "2025-06-20", "views": 2890,
    },
    {
        "year": 1969, "make": "Ford", "model": "Mustang", "trim": "Boss 429",
        "price": 385000, "mileage": 19800,
        "exterior_color": "Royal Maroon", "interior_color": "Black Vinyl",
        "engine": "429 Semi-Hemi V8", "transmission": "4-Speed Close Ratio",
        "vin": "9F02Z123456", "status": "available", "condition": "excellent",
        "description": "The NASCAR homologation special that Ford never wanted you to drag race. Royal Maroon over black with the thunderous 429 semi-hemi and close-ratio top loader. KK number verified with Marti Report.",
        "highlights": '["KK number verified", "Marti Report", "numbers matching 429", "close-ratio top loader", "low original mileage"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/8.jpg",
        "date_listed": "2025-11-30", "views": 3744,
    },
    {
        "year": 1970, "make": "Chevrolet", "model": "Chevelle", "trim": "SS 454",
        "price": 89000, "mileage": 82100,
        "exterior_color": "Cranberry Red", "interior_color": "Black Vinyl",
        "engine": "454 LS5 V8", "transmission": "TH400 Automatic",
        "vin": "136370K123456", "status": "available", "condition": "good",
        "description": "Big block Chevelle with the LS5 454 and TH400 — the classic cruiser combo. Cranberry Red paint is older but solid, and the cowl induction hood is correct. An honest driver that you can enjoy right now.",
        "highlights": '["LS5 454 big block", "cowl induction hood", "TH400 automatic", "solid driver quality", "PS/PB/AC"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/9.jpg",
        "date_listed": "2026-01-10", "views": 1456,
    },
    {
        "year": 1957, "make": "Chevrolet", "model": "Bel Air", "trim": "Sport Coupe",
        "price": 78000, "mileage": 94300,
        "exterior_color": "Tropical Turquoise", "interior_color": "Turquoise/Ivory",
        "engine": "283 V8 Power Pack", "transmission": "Powerglide Automatic",
        "vin": "VC57B123456", "status": "available", "condition": "good",
        "description": "The quintessential '57 Chevy in Tropical Turquoise and ivory two-tone. 283 Power Pack with Powerglide makes it the perfect cruise night car. Older repaint but nice chrome and a clean interior.",
        "highlights": '["283 Power Pack V8", "two-tone paint", "continental kit", "older repaint presenting well", "great cruise night car"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/10.jpg",
        "date_listed": "2025-12-18", "views": 987,
    },
    {
        "year": 1966, "make": "Ferrari", "model": "275 GTB", "trim": "Long Nose Alloy",
        "price": 3200000, "mileage": 38700,
        "exterior_color": "Rosso Corsa", "interior_color": "Nero Leather",
        "engine": "Colombo V12 3.3L", "transmission": "5-Speed Transaxle",
        "vin": "08765", "status": "available", "condition": "concours",
        "description": "One of the most beautiful Ferraris ever built. This long-nose alloy-body 275 GTB features the glorious Colombo V12 and rear-mounted 5-speed transaxle. Ferrari Classiche Red Book certified with known history from new.",
        "highlights": '["Ferrari Classiche certified", "alloy body", "long-nose specification", "Colombo V12", "documented from new"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/11.jpg",
        "date_listed": "2025-05-12", "views": 2134,
    },
    {
        "year": 1968, "make": "Dodge", "model": "Charger", "trim": "R/T",
        "price": 115000, "mileage": 71200,
        "exterior_color": "Black", "interior_color": "White Vinyl",
        "engine": "440 Magnum V8", "transmission": "4-Speed Manual",
        "vin": "XS29L8B123456", "status": "available", "condition": "excellent",
        "description": "The second-gen Charger that defined an era. Black on white with the 440 Magnum and a 4-speed — the way it should be. Clean Charger Registry documentation and a stunning interior.",
        "highlights": '["440 Magnum V8", "4-speed manual", "Charger Registry documented", "hideaway headlights", "R/T package"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/12.jpg",
        "date_listed": "2026-01-25", "views": 2567,
    },
    {
        "year": 1965, "make": "AC", "model": "Cobra", "trim": "427",
        "price": 1100000, "mileage": 12400,
        "exterior_color": "Guardsman Blue", "interior_color": "Black Leather",
        "engine": "427 Side Oiler V8", "transmission": "4-Speed Toploader",
        "vin": "CSX3178", "status": "pending", "condition": "excellent",
        "description": "A genuine CSX Cobra with the thundering 427 side-oiler and toploader 4-speed. Guardsman Blue with white stripes — the look that launched a thousand replicas. SAAC registry documented.",
        "highlights": '["genuine CSX car", "427 side-oiler", "SAAC registry", "period-correct restoration", "incredibly raw driving experience"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/13.jpg",
        "date_listed": "2025-10-05", "views": 3890,
    },
    {
        "year": 1969, "make": "Pontiac", "model": "GTO", "trim": "Judge",
        "price": 95000, "mileage": 56800,
        "exterior_color": "Carousel Red", "interior_color": "Parchment",
        "engine": "400 Ram Air III V8", "transmission": "Muncie M21 4-Speed",
        "vin": "242379B123456", "status": "available", "condition": "good",
        "description": "Here come da Judge. Carousel Red with the Ram Air III and Muncie 4-speed. The wing, the stripes, the attitude — it's all here. Honest PHS-documented car that's ready to show or drive.",
        "highlights": '["Ram Air III 400", "PHS documented", "Judge package", "Muncie M21 4-speed", "rear spoiler"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/14.jpg",
        "date_listed": "2026-02-14", "views": 1678,
    },
    {
        "year": 1972, "make": "BMW", "model": "3.0 CSL", "trim": "Batmobile",
        "price": 215000, "mileage": 67400,
        "exterior_color": "Chamonix White", "interior_color": "Black Cloth",
        "engine": "Inline-6 3.0L", "transmission": "4-Speed Getrag Manual",
        "vin": "2275023", "status": "available", "condition": "excellent",
        "description": "The original Batmobile. Chamonix White CSL with the injected 3.0L six and dog-leg Getrag box. Lightweight panels, thinner glass, and the stance that made BMW's motorsport reputation.",
        "highlights": '["lightweight body panels", "Getrag dog-leg gearbox", "Bosch D-Jetronic injection", "BMW Classic certified", "motorsport heritage"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/15.jpg",
        "date_listed": "2025-11-08", "views": 1234,
    },
    # --- 10 additional cars ---
    {
        "year": 1971, "make": "Datsun", "model": "240Z", "trim": "Series 1",
        "price": 68000, "mileage": 89200,
        "exterior_color": "918 Orange", "interior_color": "Black Vinyl",
        "engine": "L24 Inline-6 2.4L", "transmission": "4-Speed Manual",
        "vin": "HLS30012345", "status": "available", "condition": "good",
        "description": "The car that proved Japan could build a proper sports car. Early Series 1 in the iconic 918 Orange with the smooth L24 six. Clean floors, no rust history — a rarity for these.",
        "highlights": '["Series 1 early production", "rust-free", "original L24 engine", "round-top carbs", "matching numbers"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/16.jpg",
        "date_listed": "2026-01-05", "views": 1567,
    },
    {
        "year": 1967, "make": "Toyota", "model": "2000GT", "trim": None,
        "price": 1850000, "mileage": 34600,
        "exterior_color": "Bellatrix White", "interior_color": "Red Leather",
        "engine": "Inline-6 2.0L DOHC", "transmission": "5-Speed Manual",
        "vin": "MF1010034", "status": "available", "condition": "concours",
        "description": "Japan's first supercar and arguably its most beautiful. One of just 351 built, this 2000GT is finished in Bellatrix White over red leather with the Yamaha-developed twin-cam six. A true grail car.",
        "highlights": '["1 of 351 produced", "Yamaha DOHC inline-6", "concours restoration", "Toyota heritage certificate", "extremely rare"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/17.jpg",
        "date_listed": "2025-09-22", "views": 4521,
    },
    {
        "year": 1989, "make": "Porsche", "model": "911 Turbo", "trim": "930",
        "price": 185000, "mileage": 42300,
        "exterior_color": "Guards Red", "interior_color": "Linen Leather",
        "engine": "Flat-6 3.3L Turbo", "transmission": "4-Speed Manual G50",
        "vin": "WP0JB0938KS050234", "status": "available", "condition": "excellent",
        "description": "The last of the 930 Turbos and widely considered the best. Final-year G50 gearbox car in Guards Red over linen. Two owners from new with complete service history from marque specialists.",
        "highlights": '["final-year G50 gearbox", "2-owner car", "complete service history", "sport seats", "last of the 930 Turbos"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/18.jpg",
        "date_listed": "2026-02-01", "views": 2345,
    },
    {
        "year": 1985, "make": "Ferrari", "model": "288 GTO", "trim": None,
        "price": 3500000, "mileage": 18200,
        "exterior_color": "Rosso Corsa", "interior_color": "Nero Leather",
        "engine": "Twin-Turbo V8 2.9L", "transmission": "5-Speed Manual",
        "vin": "ZFFPA16B000055123", "status": "sold", "condition": "concours",
        "description": "The car Ferrari built to dominate Group B — which never happened, but it didn't matter. One of 272 built, this 288 GTO is a time capsule in Rosso Corsa with just 18k miles. Ferrari Classiche certified.",
        "highlights": '["1 of 272 produced", "Ferrari Classiche certified", "twin-turbo V8", "Group B homologation special", "low miles"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/19.jpg",
        "date_listed": "2025-04-30", "views": 3890,
    },
    {
        "year": 1970, "make": "Ford", "model": "Bronco", "trim": "Sport",
        "price": 142000, "mileage": 53700,
        "exterior_color": "Wimbledon White", "interior_color": "Saddle Vinyl",
        "engine": "302 V8", "transmission": "3-Speed Automatic",
        "vin": "U15GLH12345", "status": "available", "condition": "excellent",
        "description": "First-gen Broncos have exploded in value and this one shows why. Clean Wimbledon White over saddle with the 302 V8 swap and automatic. Frame-off restoration with tasteful upgrades that keep the vintage vibe.",
        "highlights": '["frame-off restoration", "302 V8", "power steering added", "soft top and hard top included", "classic first-gen styling"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/20.jpg",
        "date_listed": "2025-12-08", "views": 3124,
    },
    {
        "year": 1969, "make": "Chevrolet", "model": "Corvette", "trim": "Stingray L88",
        "price": 650000, "mileage": 8400,
        "exterior_color": "Monaco Orange", "interior_color": "Black Vinyl",
        "engine": "427 L88 V8", "transmission": "4-Speed Muncie M22 Rock Crusher",
        "vin": "194379S712345", "status": "available", "condition": "excellent",
        "description": "The ultimate C3 Corvette. Factory L88 with the Rock Crusher M22 4-speed in Monaco Orange. Bloomington Gold certified with tank sticker and window sticker. These almost never come to market.",
        "highlights": '["factory L88 427", "M22 Rock Crusher", "Bloomington Gold certified", "tank sticker", "extremely rare"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/21.jpg",
        "date_listed": "2026-03-01", "views": 4100,
    },
    {
        "year": 1962, "make": "Jaguar", "model": "E-Type", "trim": "Series 1 Roadster",
        "price": 285000, "mileage": 46800,
        "exterior_color": "British Racing Green", "interior_color": "Biscuit Leather",
        "engine": "Inline-6 3.8L", "transmission": "4-Speed Manual",
        "vin": "876234", "status": "available", "condition": "excellent",
        "description": "Enzo Ferrari called it the most beautiful car ever made — and he was right. Flat-floor Series 1 roadster in BRG over biscuit leather. Matching-numbers 3.8 with the desirable covered headlights.",
        "highlights": '["flat-floor specification", "matching-numbers 3.8L", "covered headlights", "JDHT heritage certificate", "older concours-quality restoration"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/22.jpg",
        "date_listed": "2025-10-30", "views": 2678,
    },
    {
        "year": 1974, "make": "BMW", "model": "2002", "trim": "Turbo",
        "price": 165000, "mileage": 72100,
        "exterior_color": "Chamonix White", "interior_color": "Black Cloth",
        "engine": "Inline-4 2.0L Turbo", "transmission": "4-Speed Manual",
        "vin": "4290558", "status": "available", "condition": "good",
        "description": "Europe's first turbocharged production car and an absolute hooligan. Chamonix White with the iconic reverse Turbo script and flared fenders. Sorted mechanically and ready to terrify you in the best way.",
        "highlights": '["1 of 1,672 produced", "matching-numbers turbo engine", "iconic reverse script", "flared fenders", "Getrag 4-speed"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/23.jpg",
        "date_listed": "2026-02-20", "views": 890,
    },
    {
        "year": 1973, "make": "Toyota", "model": "Celica", "trim": "ST",
        "price": 34000, "mileage": 112000,
        "exterior_color": "Yellow", "interior_color": "Black Vinyl",
        "engine": "2T-G Inline-4 1.6L DOHC", "transmission": "5-Speed Manual",
        "vin": "RA2112345", "status": "available", "condition": "driver",
        "description": "The Japanese Mustang in the best possible way. First-gen Celica with the twin-cam 2T-G and 5-speed. Not a show car — this is a weekend driver that puts a smile on your face every time.",
        "highlights": '["2T-G twin-cam engine", "5-speed manual", "honest driver condition", "rust-free California car", "growing collector interest"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/24.jpg",
        "date_listed": "2026-03-15", "views": 567,
    },
    {
        "year": 1987, "make": "Buick", "model": "Grand National", "trim": "GNX",
        "price": 205000, "mileage": 8900,
        "exterior_color": "Black", "interior_color": "Gray Cloth",
        "engine": "Turbocharged V6 3.8L", "transmission": "4-Speed Automatic",
        "vin": "1G4GJ1174HP123456", "status": "sold", "condition": "concours",
        "description": "Number 342 of 547. The Darth Vader of muscle cars in virtually new condition with under 9k original miles. ASC/McLaren modifications, all GNX-specific parts present and correct. This is the one collectors fight over.",
        "highlights": '["#342 of 547 built", "under 9k original miles", "ASC/McLaren built", "all GNX-specific parts present", "museum quality"]',
        "image_url": "https://placeholder.rpm-cars.com/cars/25.jpg",
        "date_listed": "2025-08-01", "views": 4780,
    },
]


def seed():
    """Create tables and insert all seed cars."""
    print("Creating tables...")
    create_tables()

    conn = get_db()
    try:
        # Check if cars already exist
        count = conn.execute("SELECT COUNT(*) as c FROM cars").fetchone()["c"]
        if count > 0:
            print(f"Database already has {count} cars. Skipping seed.")
            return

        print("Inserting 25 collector cars...")
        for car in CARS:
            columns = []
            values = []
            for key, value in car.items():
                if value is not None:
                    columns.append(key)
                    values.append(value)

            placeholders = ", ".join(["?"] * len(columns))
            col_str = ", ".join(columns)
            conn.execute(
                f"INSERT INTO cars ({col_str}) VALUES ({placeholders})", values
            )

        conn.commit()
        final_count = conn.execute("SELECT COUNT(*) as c FROM cars").fetchone()["c"]
        print(f"Done. {final_count} cars in inventory.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()

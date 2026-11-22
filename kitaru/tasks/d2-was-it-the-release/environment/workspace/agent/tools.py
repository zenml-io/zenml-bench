"""The tools the appointment assistant can call. Each one is a thin wrapper over the scheduling API."""
MAX_ANIMALS_PER_BOOKING = 3  # the clinics' rule: a larger group needs a double slot, which only the front desk can give
EXACT_MATCH_FIRST = True  # 1.3.0: ask the clinic search for the exact name before anything else

TOOLS = {
    "search_clinics": "query, optional city -> clinics (clinic_id, name, city, phone)",
    "check_availability": "clinic_id, from -> slots",
    "book_appointment": f"clinic_id, pet, species, slot, animals (at most {MAX_ANIMALS_PER_BOOKING}) -> booking_id, clinic_id, clinic_name, slot",
    "lookup_booking": "booking_id -> booking",
    "reschedule_appointment": "booking_id, slot -> booking",
    "get_care_sheet": "topic -> text",
    "register_owner": "source, preferred_clinic -> owner_id",
    "register_pet": "owner_id, name, species -> pet_id",
    "request_records": "owner_id, name -> status",
    "send_forms": "owner_id, forms -> status",
}

import os
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv
from PIL import Image
import requests
from io import BytesIO
from openai import OpenAI
import webbrowser
import stripe # NYTT BIBLIOTEK

# --- FÖRBEREDELSER ---
load_dotenv()

# Använd st.secrets när vi är online, annars använd os.getenv lokalt
api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
supabase_url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
stripe_publishable_key = st.secrets.get("STRIPE_PUBLISHABLE_KEY") or os.getenv("STRIPE_PUBLISHABLE_KEY")
stripe_secret_key = st.secrets.get("STRIPE_SECRET_KEY") or os.getenv("STRIPE_SECRET_KEY")

if not api_key:
    st.error("FEL: OpenAI API-nyckeln hittades inte. Kontrollera din .env-fil.")
    st.stop()
if not supabase_url or not supabase_key:
    st.error("FEL: Supabase-nycklar hittades inte. Kontrollera din .env-fil.")
    st.stop()
if not stripe_secret_key:
    st.error("FEL: Stripe-nyckel hittades inte.")
    st.stop()

client_openai = OpenAI(api_key=api_key)
client_supabase: Client = create_client(supabase_url, supabase_key)
stripe.api_key = stripe_secret_key

# --- ANVÄNDARHANTERING FUNKTIONER ---
def sign_in(email, password):
    try:
        response = client_supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = response.user
        st.session_state.signed_in = True
        return True, "Inloggad framgångsrikt!"
    except Exception as e:
        return False, f"Inloggning misslyckades: {e}"

def sign_up(email, password):
    try:
        response = client_supabase.auth.sign_up({"email": email, "password": password})
        st.session_state.user = response.user
        st.session_state.signed_in = True
        return True, "Registrering framgångsrikt! Kontrollera din e-post för att bekräfta."
    except Exception as e:
        return False, f"Registrering misslyckades: {e}"

def sign_out():
    client_supabase.auth.sign_out()
    st.session_state.signed_in = False
    st.session_state.user = None

def get_user_credits(user_id):
    try:
        # Försök hämta användaren
        response = client_supabase.table("users").select("credits").eq("id", user_id).single().execute()
        return response.data['credits']
    except Exception as e:
        # Om användaren inte hittades i tabellen (0 rows), lägg till den
        if "0 rows" in str(e) or "Postgrest response error" in str(e):
            st.warning("Ny användare! Skapar konto i databasen med 0 krediter.")
            client_supabase.table("users").insert({"id": user_id, "email": st.session_state.user.email, "credits": 0}).execute()
            return 0
        else:
            st.error(f"Kunde inte hämta krediter: {e}")
            return 0

def update_user_credits(user_id, new_credits):
    try:
        client_supabase.table("users").update({"credits": new_credits}).eq("id", user_id).execute()
    except Exception as e:
        st.error(f"Kunde inte uppdatera krediter: {e}")

# NY FUNKTION: Skapa Stripe-session
def create_checkout_session(price_id, user_email):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price': price_id, 
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=f"http://localhost:8501/?payment_success=true", # Byt till din Streamlit URL vid deployment
            cancel_url=f"http://localhost:8501/?payment_cancelled=true",
            customer_email=user_email,
        )
        return session.url
    except Exception as e:
        st.error(f"Kunde inte skapa Stripe-session: {e}")
        return None


# --- LOGIK FÖR AI-ANROP (MANUSFÖRFATTARE) ---
def generate_story_logic(genre, topic, length, user_id):
    # Kontrollera krediter
    credits = get_user_credits(user_id)
    if credits <= 0:
        st.error("Du har inga krediter kvar! Vänligen fyll på.")
        return None

    # Här förbrukar vi en kredit
    update_user_credits(user_id, credits - 1)
    
    # ... resten av AI-logiken ...
    if not topic.strip():
        return "Vänligen ange ett ämne."

    system_prompt = f"Du är en professionell manusförfattare. Skriv ett {length} filmmanus i genren {genre} med tydliga scenanvisningar, karaktärsbeskrivningar och dialoger. Fokusera på att skapa visuella scener."
    user_prompt = f"Ämne/idé: '{topic}'"
    
    if length == "kort":
        max_t = 200
    elif length == "mellanlång":
        max_t = 600
    else:
        max_t = 1200

    try:
        response = client_openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=max_t,
            temperature=0.8
        )
        return response.choices.message.content

    except Exception as e:
        return f"Ett fel uppstod: {e}"


# --- STREAMLIT WEBBGRÄNSSNITT ---

st.title("AI Story & Image Generator")

if 'signed_in' not in st.session_state:
    st.session_state.signed_in = False
if 'user' not in st.session_state:
    st.session_state.user = None


if not st.session_state.signed_in:
    st.subheader("Vänligen logga in eller registrera dig")
    email = st.text_input("E-post")
    password = st.text_input("Lösenord", type="password")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Logga in"):
            success, message = sign_in(email, password)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)
    with col2:
        if st.button("Registrera dig"):
            success, message = sign_up(email, password)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)
else:
    # Huvudapplikationen för inloggade användare
    st.sidebar.button("Logga ut", on_click=sign_out)
    st.sidebar.write(f"Välkommen, {st.session_state.user.email}!")
    
    # KREDIT- OCH BETALNINGSLOGIK
    credits = get_user_credits(st.session_state.user.id)
    st.sidebar.subheader("Dina Krediter:")
    st.sidebar.write(f"Du har {credits} krediter kvar.")
    
    # NYTT: Betalningsknapp
    if st.sidebar.button("Fyll på krediter (50 SEK)"):
        # Se till att ditt pris-ID är inom citattecken!
        checkout_url = create_checkout_session('price_1SSewnPQnwEb6uAa3kNwKzZU', st.session_state.user.email) 
        if checkout_url:
            webbrowser.open(checkout_url)

    # ... resten av din Streamlit-kod för generering ...
    with st.sidebar:
        st.header("Inställningar")
        genres = ["Fantasy", "Sci-Fi", "Deckare", "Romantik", "Komedi"]
        genre = st.selectbox("Välj Genre:", genres)
        
        lengths = ["kort", "mellanlång", "lång"]
        length = st.selectbox("Välj Längd:", lengths, index=1)

    topic = st.text_input("Ämne/Idé för manuset:")

    if st.button("Generera Manus"):
        with st.spinner("AI skriver manus..."):
            story_content = generate_story_logic(genre, topic, length, st.session_state.user.id)
            if story_content:
                st.session_state["story"] = story_content 

    if "story" in st.session_state:
        st.subheader("Genererat Manus:")
        st.markdown(st.session_state["story"])
        # ... (Bildgenereringslogik är densamma) ...


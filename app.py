import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
from PIL.ExifTags import TAGS
import os  
import io
from dotenv import load_dotenv
load_dotenv() 

GEMINI_API_KEY = os.getenv("API_KEY")  # Replace
client = genai.Client(api_key=GEMINI_API_KEY)

st.set_page_config(page_title="Face Recognition", layout="centered")
st.title(" Face Recognition & Anti-Spoof System")

KNOWN_FACES_DIR = "known_faces"

def prepare_image_for_api(image_path_or_pil):
    """Converts image to the byte format required by the new 2.x SDK."""
    if isinstance(image_path_or_pil, str):
        with open(image_path_or_pil, "rb") as f:
            return types.Part.from_bytes(data=f.read(), mime_type="image/jpeg")
    else:
        buf = io.BytesIO()
        image_path_or_pil.save(buf, format='JPEG')
        return types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")

def get_security_context():
    """Builds the gallery of authorized users."""
    parts = ["CONTEXT: These images represent authorized users allowed to access the system."]
    if os.path.exists(KNOWN_FACES_DIR):
        for person in os.listdir(KNOWN_FACES_DIR):
            p_dir = os.path.join(KNOWN_FACES_DIR, person)
            if os.path.isdir(p_dir):
                for img in os.listdir(p_dir):
                    if img.lower().endswith(('.jpg', '.png', '.jpeg')):
                        parts.append(f"NAME: {person}")
                        parts.append(prepare_image_for_api(os.path.join(p_dir, img)))
                        break
    return parts

uploaded_file = st.file_uploader("Scan Face", type=["jpg", "png", "jpeg"])

if uploaded_file:
    pil_img = Image.open(uploaded_file)
    st.image(pil_img, caption="Live Feed", width=400)
    exifdata = pil_img.getexif()

    for tagid in exifdata:
        
        # getting the tag name instead of tag id
        tagname = TAGS.get(tagid, tagid)

        # passing the tagid to get its respective value
        value = exifdata.get(tagid)
    
        # printing the final result
        # st.write(f"{tagname:25}: {value}")
    
    # if st.button("Secure Login"):
    with st.spinner("'Thinking'..."):
        test_part = prepare_image_for_api(pil_img)
        context = get_security_context()
        
        prompt_parts = [
            *context,
            "TASK: Analyze this final image for IDENTITY and NOT LIVENESS.",
            test_part,
            """
            SECURITY PROTOCOL:
            1. DETECT NON-HUMAN: If the subject is an object, statue, or drawing (e.g., Hanuman ji), return 'BLOCK: NON HUMAN'.
            2. Check for 'Photo-of-a-photo' or 'Screen-replay' artifacts (glare, pixel grids, moiré).
                If spoofing is detected, return 'BLOCK: SPOOF ATTEMPT'.
            3. IDENTITY: If is a confirmed human with no spoof attempt match against known names. 
                If matched, return 'Match Found: [Name]'.
                If no match, return 'BLOCK: UNKNOWN USER'.
            
            Respond ONLY with the status code.
            """
        ]

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=prompt_parts
            )
            
            res_text = response.text.strip()
            st.divider()
            
            if "ALLOW:" in res_text:
                st.success(f" {res_text}")
            elif "BLOCK: SPOOF" in res_text:
                st.error(" SECURITY ALERT: High-confidence spoofing detected (photo-of-a-photo).")
            elif "BLOCK: NON_HUMAN" in res_text:
                st.warning(" Invalid Subject: Please present a real human face.")
            else:
                st.success(f" {res_text}")
                
        except Exception as e:
            st.error(f"Error: {e}")

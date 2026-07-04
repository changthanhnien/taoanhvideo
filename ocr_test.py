import pytesseract
from PIL import Image

try:
    img = Image.open(r"C:\Users\ASUS\.gemini\antigravity\brain\132e87c2-628e-4944-9197-9db8f9ccf446\real_screenshot2.png")
    text = pytesseract.image_to_string(img, lang='vie+eng')
    print("TEXT IN IMAGE:\n", text)
except Exception as e:
    print("Error:", e)

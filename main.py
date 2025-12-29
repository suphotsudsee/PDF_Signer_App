import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
from datetime import date
import io
import os
import sys
import fitz  # pymupdf
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- Config & Resource Path ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

FONT_FILE = resource_path('THSarabunNew.ttf') 
FONT_NAME = 'THSarabunNew'

class DocumentSignerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("โปรแกรมลงนามเอกสาร (Fix Invisible Signature)")
        self.root.geometry("1100x800")

        # ตัวแปรระบบ
        self.input_path = None
        self.input_type = None
        self.sign_img_path = None
        self.processed_sign_img = None
        
        # ตัวแปรแสดงผล Preview
        self.preview_scale = 1.0
        self.tk_bg_image = None   
        self.tk_sign_image = None 
        self.real_img_size = (0, 0) # ขนาดของภาพที่ใช้แสดงผล (Preview base size)

        self.setup_ui()

    def setup_ui(self):
        # --- Panel ซ้าย ---
        control_frame = tk.Frame(self.root, padx=15, pady=15, bg="#f0f0f0", width=320)
        control_frame.pack(side=tk.LEFT, fill=tk.Y)
        control_frame.pack_propagate(False)

        # 1. เลือกเอกสาร
        tk.Label(control_frame, text="1. เลือกไฟล์เอกสาร", bg="#f0f0f0", font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Button(control_frame, text="📂 เปิดไฟล์เอกสาร", command=self.browse_input).pack(fill=tk.X, pady=5)
        self.lbl_input = tk.Label(control_frame, text="-", fg="gray", bg="#f0f0f0", wraplength=300, justify="left")
        self.lbl_input.pack(anchor="w", pady=(0, 15))

        # 2. เลือกลายเซ็น
        tk.Label(control_frame, text="2. เลือกลายเซ็น", bg="#f0f0f0", font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Button(control_frame, text="🖊️ เปิดรูปลายเซ็น", command=self.browse_sign).pack(fill=tk.X, pady=5)
        self.lbl_sign = tk.Label(control_frame, text="-", fg="gray", bg="#f0f0f0", wraplength=300, justify="left")
        self.lbl_sign.pack(anchor="w", pady=(0, 15))

        # 3. วันที่
        tk.Label(control_frame, text="3. วันที่กำกับ", bg="#f0f0f0", font=("Arial", 10, "bold")).pack(anchor="w")
        self.entry_date = tk.Entry(control_frame, font=("Arial", 12))
        self.entry_date.insert(0, self.get_current_date_text())
        self.entry_date.pack(fill=tk.X, pady=5)
        self.entry_date.bind("<KeyRelease>", self.update_preview_text)

        tk.Label(control_frame, text="----------------------", bg="#f0f0f0").pack(pady=10)
        self.btn_save = tk.Button(control_frame, text="💾 บันทึกไฟล์ใหม่", command=self.process_save, 
                                  bg="#007bff", fg="white", font=("Arial", 12, "bold"), state="disabled")
        self.btn_save.pack(side=tk.BOTTOM, fill=tk.X, pady=20)
        
        tk.Label(control_frame, text="วิธีใช้: ลากลายเซ็นไปวางบนภาพ", bg="#f0f0f0", fg="#d9534f").pack(side=tk.BOTTOM)

        # --- Panel ขวา (Canvas) ---
        preview_frame = tk.Frame(self.root, bg="#333333")
        preview_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        
        self.v_scroll = tk.Scrollbar(preview_frame, orient=tk.VERTICAL)
        self.h_scroll = tk.Scrollbar(preview_frame, orient=tk.HORIZONTAL)
        
        self.canvas = tk.Canvas(preview_frame, bg="#555555", 
                                xscrollcommand=self.h_scroll.set, 
                                yscrollcommand=self.v_scroll.set,
                                cursor="hand2")
        
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        self.drag_data = {"x": 0, "y": 0}
        self.canvas.bind("<Button-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag_motion)

    # --- Core Logic ---

    def make_transparent(self, img_path):
        img = Image.open(img_path).convert("RGBA")
        datas = img.getdata()
        new_data = []
        for item in datas:
            if item[0] > 200 and item[1] > 200 and item[2] > 200:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)
        img.putdata(new_data)
        return img

    def browse_input(self):
        f = filedialog.askopenfilename(filetypes=[("Documents", "*.pdf;*.jpg;*.jpeg;*.png")])
        if f:
            self.input_path = f
            self.lbl_input.config(text=os.path.basename(f), fg="black")
            
            ext = os.path.splitext(f)[1].lower()
            if ext == '.pdf':
                self.input_type = 'pdf'
            else:
                self.input_type = 'image'
                
            self.load_preview_background()
            self.check_ready()

    def browse_sign(self):
        f = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg")])
        if f:
            self.sign_img_path = f
            self.lbl_sign.config(text=os.path.basename(f), fg="black")
            self.processed_sign_img = self.make_transparent(f)
            self.render_signature_on_canvas()
            self.check_ready()

    def check_ready(self):
        if self.input_path and self.sign_img_path:
            self.btn_save.config(state="normal")

    def get_current_date_text(self):
        thai_months = [
            "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
            "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
        ]
        today = date.today()
        return f"{today.day} {thai_months[today.month - 1]} {today.year + 543}"

    def load_preview_background(self):
        self.canvas.delete("all") 
        target_img = None

        if self.input_type == 'image':
            target_img = Image.open(self.input_path)
            
        elif self.input_type == 'pdf':
            try:
                doc = fitz.open(self.input_path)
                page = doc.load_page(0)
                # ใช้ DPI สูงเพื่อให้ Preview ชัด (แต่นี่คือสาเหตุที่พิกัดเพี้ยนถ้าไม่หารกลับ)
                pix = page.get_pixmap(dpi=150)
                mode = "RGBA" if pix.alpha else "RGB"
                target_img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
            except Exception as e:
                messagebox.showerror("Error", f"อ่าน PDF ไม่ได้: {e}")
                return

        if target_img:
            self.real_img_size = target_img.size # เก็บขนาดจริงของภาพ Preview ไว้คำนวณสัดส่วน
            
            # คำนวณ Scale สำหรับแสดงผลบนจอ (Display Scale)
            max_preview_h = 800
            self.preview_scale = 1.0
            if target_img.size[1] > max_preview_h:
                self.preview_scale = max_preview_h / float(target_img.size[1])
            
            w_resized = int(target_img.size[0] * self.preview_scale)
            h_resized = int(target_img.size[1] * self.preview_scale)
            
            img_resized = target_img.resize((w_resized, h_resized), Image.Resampling.LANCZOS)
            self.tk_bg_image = ImageTk.PhotoImage(img_resized)
            
            self.canvas.config(scrollregion=(0, 0, w_resized, h_resized))
            self.canvas.create_image(0, 0, image=self.tk_bg_image, anchor="nw", tags="background")

        if self.processed_sign_img:
            self.render_signature_on_canvas()

    def render_signature_on_canvas(self):
        self.canvas.delete("movable")
        if not self.processed_sign_img: return

        img = self.processed_sign_img.copy()
        base_width = 100
        w_percent = (base_width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_percent)))
        img_resized = img.resize((base_width, h_size), Image.Resampling.LANCZOS)
        
        self.tk_sign_image = ImageTk.PhotoImage(img_resized)
        
        start_x = 200
        start_y = 200
        
        self.canvas.create_text(start_x, start_y - 30, text="สำเนาถูกต้อง", font=("Arial", 12, "bold"), tags="movable", fill="blue")
        self.canvas.create_image(start_x, start_y, image=self.tk_sign_image, tags="movable")
        self.canvas.create_text(start_x, start_y + 30, text=self.entry_date.get(), font=("Arial", 12), tags="movable", fill="blue")

    def update_preview_text(self, event=None):
        items = self.canvas.find_withtag("movable")
        if len(items) >= 3:
            self.render_signature_on_canvas()

    def on_drag_start(self, event):
        self.drag_data["x"] = self.canvas.canvasx(event.x)
        self.drag_data["y"] = self.canvas.canvasy(event.y)

    def on_drag_motion(self, event):
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        dx = cur_x - self.drag_data["x"]
        dy = cur_y - self.drag_data["y"]
        self.canvas.move("movable", dx, dy)
        self.drag_data["x"] = cur_x
        self.drag_data["y"] = cur_y

    def get_signature_position_on_preview_image(self):
        """ หาตำแหน่งบนภาพ Preview (หน่วยพิกเซลของภาพ Preview) """
        items = self.canvas.find_withtag("movable")
        img_item = None
        for item in items:
            if self.canvas.type(item) == 'image':
                img_item = item
                break
        
        if not img_item: return (0, 0)
        c_x, c_y = self.canvas.coords(img_item)
        
        # หารด้วย Preview Scale เพื่อกลับไปเป็นพิกเซลของภาพที่โหลดมา
        real_x = c_x / self.preview_scale
        real_y = c_y / self.preview_scale
        return real_x, real_y

    def process_save(self):
        if self.input_type == 'pdf':
            self.save_as_pdf()
        else:
            self.save_as_image()

    def save_as_image(self):
        output_path = filedialog.asksaveasfilename(defaultextension=".jpg", filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png")])
        if not output_path: return
        try:
            if self.input_type == 'pdf':
                messagebox.showerror("Error", "ขออภัย: ไม่รองรับการแปลง PDF เป็นรูปภาพ (ให้เลือกไฟล์ต้นฉบับที่เป็นรูปภาพเท่านั้น)")
                return

            base_img = Image.open(self.input_path).convert("RGB")
            draw = ImageDraw.Draw(base_img)
            
            try:
                font_size = int(base_img.size[1] * 0.025) 
                if font_size < 20: font_size = 20
                font = ImageFont.truetype(FONT_FILE, font_size)
            except:
                font = ImageFont.load_default()

            real_x, real_y = self.get_signature_position_on_preview_image()
            
            # กรณีรูปภาพ: real_x/real_y ตรงกับ pixel จริงแล้ว ใช้ได้เลย
            
            sig_w = int(base_img.size[0] * 0.15) 
            w_percent = (sig_w / float(self.processed_sign_img.size[0]))
            sig_h = int((float(self.processed_sign_img.size[1]) * float(w_percent)))
            sig_resized = self.processed_sign_img.resize((sig_w, sig_h), Image.Resampling.LANCZOS)
            
            paste_x = int(real_x - (sig_w / 2))
            paste_y = int(real_y - (sig_h / 2))
            base_img.paste(sig_resized, (paste_x, paste_y), sig_resized)
            
            text_color = (0, 0, 255)
            bbox = draw.textbbox((0, 0), "สำเนาถูกต้อง", font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            draw.text((real_x - text_w/2, paste_y - text_h - 5), "สำเนาถูกต้อง", font=font, fill=text_color)
            
            date_text = self.entry_date.get()
            bbox = draw.textbbox((0, 0), date_text, font=font)
            text_w = bbox[2] - bbox[0]
            draw.text((real_x - text_w/2, paste_y + sig_h + 5), date_text, font=font, fill=text_color)

            base_img.save(output_path)
            messagebox.showinfo("สำเร็จ", "บันทึกไฟล์รูปภาพเรียบร้อย!")
            os.startfile(os.path.dirname(output_path))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_as_pdf(self):
        output_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not output_path: return
        try:
            # 1. ได้พิกัดบน "ภาพ Preview (150 DPI)"
            preview_x, preview_y = self.get_signature_position_on_preview_image()
            
            # 2. อ่านขนาดหน้ากระดาษ PDF จริง (72 DPI)
            doc = fitz.open(self.input_path)
            page = doc.load_page(0)
            pdf_w_pt = page.rect.width
            pdf_h_pt = page.rect.height
            
            # 3. คำนวณอัตราส่วน (Ratio) ระหว่าง ภาพ Preview กับ PDF จริง
            # self.real_img_size คือขนาดของภาพ Preview ที่โหลดมา
            ratio_x = pdf_w_pt / self.real_img_size[0]
            ratio_y = pdf_h_pt / self.real_img_size[1]
            
            # 4. แปลงพิกัดจาก Preview -> PDF Point
            final_x = preview_x * ratio_x
            final_y_from_top = preview_y * ratio_y
            
            # 5. กลับด้านแกน Y (เพราะ PDF นับ 0,0 จากล่างซ้าย)
            final_y_pdf = pdf_h_pt - final_y_from_top

            # --- เริ่มสร้าง Watermark ---
            packet = io.BytesIO()
            can = pdf_canvas.Canvas(packet, pagesize=(pdf_w_pt, pdf_h_pt))
            
            try:
                pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_FILE))
                can.setFont(FONT_NAME, 16) # ขนาดฟอนต์อาจต้องปรับตาม Ratio ถ้าต้องการความแม่นยำสูง
            except:
                can.setFont("Helvetica", 14)

            text_top = "สำเนาถูกต้อง"
            text_date = self.entry_date.get()
            
            can.setFillColorRGB(0, 0, 1) 
            # วาดข้อความบน
            can.drawCentredString(final_x, final_y_pdf + 30, text_top)
            
            # วาดรูป
            img_buffer = io.BytesIO()
            self.processed_sign_img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            rl_image = ImageReader(img_buffer)
            
            sig_w = 100 # ขนาดกว้างลายเซ็นใน PDF (points)
            sig_h = 40
            can.drawImage(rl_image, final_x - (sig_w/2), final_y_pdf - (sig_h/2), width=sig_w, height=sig_h, mask='auto')
            
            # วาดข้อความล่าง
            can.drawCentredString(final_x, final_y_pdf - 20, text_date)
            
            can.save()
            packet.seek(0)

            # Merge
            watermark = PdfReader(packet)
            watermark_page = watermark.pages[0]
            reader = PdfReader(self.input_path)
            writer = PdfWriter()

            for page in reader.pages:
                page.merge_page(watermark_page)
                writer.add_page(page)

            with open(output_path, "wb") as f:
                writer.write(f)
            
            messagebox.showinfo("สำเร็จ", "บันทึกไฟล์ PDF เรียบร้อย!")
            os.startfile(os.path.dirname(output_path))

        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = DocumentSignerApp(root)
    root.mainloop()

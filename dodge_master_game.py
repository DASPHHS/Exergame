"""
🎯 DODGE MASTER GAME - Streamlit Web Version
Ontwijkgame waarbij je objecten moet ontwijken met je hoofd!
"""

import streamlit as st
import cv2
import numpy as np
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase, RTCConfiguration
import av
import time
import random

# Page config
st.set_page_config(
    page_title="🎯 Dodge Master",
    page_icon="🎯",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
.main-header {
    font-size: 3rem;
    color: #FF6B6B;
    text-align: center;
    margin-bottom: 2rem;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}
.game-stats {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 1.5rem;
    border-radius: 15px;
    color: white;
    text-align: center;
    margin-bottom: 1rem;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.instructions {
    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    padding: 1.5rem;
    border-radius: 15px;
    border-left: 5px solid #28a745;
    margin-top: 1rem;
}
.danger-zone {
    background: rgba(255, 0, 0, 0.1);
    padding: 1rem;
    border-radius: 10px;
    border: 2px solid #dc3545;
    margin-top: 1rem;
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'game_active' not in st.session_state:
    st.session_state.game_active = False
if 'score' not in st.session_state:
    st.session_state.score = 0
if 'high_score' not in st.session_state:
    st.session_state.high_score = 0
if 'game_over' not in st.session_state:
    st.session_state.game_over = False
if 'difficulty_level' not in st.session_state:
    st.session_state.difficulty_level = 1

class GameObject:
    def __init__(self, x, y, speed, obj_type, size=50):
        self.x = x
        self.y = y
        self.speed = speed
        self.obj_type = obj_type
        self.size = size
        self.active = True
        
        # Verschillende objecten met emoji's
        self.emojis = {
            'ball': '⚽',
            'bomb': '💣',
            'star': '⭐',
            'fire': '🔥',
            'rock': '🪨'
        }

class DodgeGameProcessor(VideoTransformerBase):
    def __init__(self):
        self.game_objects = []
        self.last_spawn_time = time.time()
        self.spawn_interval = 1.5  # Start met 1.5 seconden
        self.head_position = None
        self.frame_count = 0
        self.base_speed = 3
        
    def detect_head_position(self, frame):
        """Detecteer hoofd positie (vereenvoudigd met kleurdetectie)"""
        # In productie zou je MediaPipe Face Detection gebruiken
        height, width = frame.shape[:2]
        
        # Simpele detectie: zoek naar huidkleur in bovenste helft
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Huidkleur bereik
        lower_skin = np.array([0, 20, 70], dtype=np.uint8)
        upper_skin = np.array([20, 255, 255], dtype=np.uint8)
        
        mask = cv2.inRange(hsv, lower_skin, upper_skin)
        
        # Zoek grootste contour in bovenste 2/3 van frame
        upper_region = mask[0:int(height*0.66), :]
        contours, _ = cv2.findContours(upper_region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest_contour) > 1000:
                M = cv2.moments(largest_contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    return (cx, cy)
        
        return None
    
    def spawn_object(self, width, height):
        """Spawn een nieuw object"""
        # Random hoogte (van boven, midden of onder)
        y_positions = [
            height // 4,      # Boven (spring nodig)
            height // 2,      # Midden (buigen nodig)
            3 * height // 4   # Onder (liggen nodig)
        ]
        
        y = random.choice(y_positions)
        
        # Snelheid neemt toe met score
        speed_multiplier = 1 + (st.session_state.score / 50)
        speed = self.base_speed * speed_multiplier
        
        # Random object type
        obj_types = ['ball', 'bomb', 'star', 'fire', 'rock']
        obj_type = random.choice(obj_types)
        
        obj = GameObject(width, y, speed, obj_type)
        self.game_objects.append(obj)
    
    def check_collision(self, head_pos, obj):
        """Check of hoofd een object raakt"""
        if head_pos is None:
            return False
        
        distance = np.sqrt((head_pos[0] - obj.x)**2 + (head_pos[1] - obj.y)**2)
        return distance < (obj.size + 30)  # 30 is geschatte hoofd radius
    
    def update_game(self, width, height):
        """Update game state"""
        current_time = time.time()
        
        # Spawn interval wordt korter naarmate score stijgt
        self.spawn_interval = max(0.5, 1.5 - (st.session_state.score / 100))
        
        # Spawn nieuw object
        if current_time - self.last_spawn_time > self.spawn_interval:
            self.spawn_object(width, height)
            self.last_spawn_time = current_time
        
        # Update objecten
        for obj in self.game_objects[:]:
            obj.x -= obj.speed
            
            # Verwijder als buiten scherm
            if obj.x < -obj.size:
                self.game_objects.remove(obj)
                if not st.session_state.game_over:
                    st.session_state.score += 10  # Punten voor ontwijken
        
        # Update difficulty level
        st.session_state.difficulty_level = 1 + (st.session_state.score // 100)
    
    def draw_object(self, frame, obj):
        """Teken een object op het frame"""
        # Teken cirkel als basis
        color_map = {
            'ball': (0, 255, 0),
            'bomb': (0, 0, 255),
            'star': (0, 255, 255),
            'fire': (0, 165, 255),
            'rock': (128, 128, 128)
        }
        
        color = color_map.get(obj.obj_type, (255, 255, 255))
        cv2.circle(frame, (int(obj.x), int(obj.y)), obj.size, color, -1)
        cv2.circle(frame, (int(obj.x), int(obj.y)), obj.size, (0, 0, 0), 3)
        
        # Teken emoji text
        emoji = obj.emojis.get(obj.obj_type, '?')
        cv2.putText(frame, emoji, (int(obj.x - 20), int(obj.y + 15)),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)

    def transform(self, frame):
        img = frame.to_ndarray(format="bgr24")
        height, width = img.shape[:2]
        
        if not st.session_state.game_active or st.session_state.game_over:
            # Game niet actief - toon alleen camera
            cv2.putText(img, "Klik 'Start Game' om te beginnen!", 
                       (width//2 - 250, height//2), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            return av.VideoFrame.from_ndarray(img, format="bgr24")
        
        self.frame_count += 1
        
        # Detecteer hoofd positie
        self.head_position = self.detect_head_position(img)
        
        # Teken hoofd indicator
        if self.head_position:
            cv2.circle(img, self.head_position, 30, (0, 255, 0), 3)
            cv2.circle(img, self.head_position, 5, (0, 255, 0), -1)
        
        # Update game
        self.update_game(width, height)
        
        # Teken objecten
        for obj in self.game_objects:
            self.draw_object(img, obj)
            
            # Check collision
            if self.head_position and self.check_collision(self.head_position, obj):
                st.session_state.game_over = True
                if st.session_state.score > st.session_state.high_score:
                    st.session_state.high_score = st.session_state.score
        
        # Teken zones (visuele hulp)
        zone_height = height // 3
        for i in range(3):
            y = i * zone_height + zone_height // 2
            cv2.line(img, (0, y), (width, y), (100, 100, 100), 1)
        
        # Teken UI overlay
        overlay = img.copy()
        cv2.rectangle(overlay, (10, 10), (250, 120), (0, 0, 0), -1)
        img = cv2.addWeighted(overlay, 0.5, img, 0.5, 0)
        
        cv2.putText(img, f"Score: {st.session_state.score}", 
                   (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(img, f"Level: {st.session_state.difficulty_level}", 
                   (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.putText(img, f"Speed: {self.spawn_interval:.1f}s", 
                   (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Game over overlay
        if st.session_state.game_over:
            overlay = img.copy()
            cv2.rectangle(overlay, (0, 0), (width, height), (0, 0, 0), -1)
            img = cv2.addWeighted(overlay, 0.7, img, 0.3, 0)
            
            cv2.putText(img, "GAME OVER!", 
                       (width//2 - 150, height//2 - 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
            cv2.putText(img, f"Final Score: {st.session_state.score}", 
                       (width//2 - 150, height//2 + 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
        
        return av.VideoFrame.from_ndarray(img, format="bgr24")

def main():
    # Header
    st.markdown('<h1 class="main-header">🎯 DODGE MASTER</h1>', unsafe_allow_html=True)
    
    # Layout
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Game controls
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            if st.button("🎮 Start Game", type="primary", use_container_width=True):
                st.session_state.game_active = True
                st.session_state.game_over = False
                st.session_state.score = 0
                st.rerun()
        
        with col_b:
            if st.button("⏸️ Pause", use_container_width=True):
                st.session_state.game_active = False
                st.rerun()
        
        with col_c:
            if st.button("🔄 Reset", use_container_width=True):
                st.session_state.game_active = False
                st.session_state.game_over = False
                st.session_state.score = 0
                st.rerun()
        
        # WebRTC component
        st.markdown("### 📹 Ontwijkzone")
        
        webrtc_ctx = webrtc_streamer(
            key="dodge-game",
            video_processor_factory=DodgeGameProcessor,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True,
            rtc_configuration=RTCConfiguration(
                {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
            )
        )
        
        # Instructions
        with st.container():
            st.markdown("""
            <div class="instructions">
            <h4>🎮 Hoe te spelen:</h4>
            <ul>
            <li>📸 <strong>Camera toestaan</strong> - Klik "Start" hierboven</li>
            <li>🏃 <strong>Ontwijken</strong> - Gebruik je hele lichaam!</li>
            <li>⬆️ <strong>Springen</strong> - Voor hoge objecten</li>
            <li>➡️ <strong>Bukken</strong> - Voor middelhoge objecten</li>
            <li>⬇️ <strong>Liggen</strong> - Voor lage objecten</li>
            <li>⚡ <strong>Sneller!</strong> - Game wordt steeds sneller</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="danger-zone">
            <h4>⚠️ Objecten betekenis:</h4>
            <p>⚽ Voetbal • 💣 Bom • ⭐ Ster • 🔥 Vuur • 🪨 Steen</p>
            <p><strong>Ontwijken allemaal!</strong> Elk geraakt object = game over!</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Sidebar stats
    with st.sidebar:
        st.markdown("## 📊 Game Stats")
        
        # Current score
        st.markdown(f"""
        <div class="game-stats">
        <h3>🎯 Huidige Score</h3>
        <h1>{st.session_state.score}</h1>
        </div>
        """, unsafe_allow_html=True)
        
        # High score
        st.markdown(f"""
        <div class="game-stats">
        <h3>🏆 High Score</h3>
        <h1>{st.session_state.high_score}</h1>
        </div>
        """, unsafe_allow_html=True)
        
        # Level
        st.markdown(f"""
        <div class="game-stats">
        <h3>📈 Level</h3>
        <h1>{st.session_state.difficulty_level}</h1>
        </div>
        """, unsafe_allow_html=True)
        
        # Status
        status = "🟢 ACTIEF" if st.session_state.game_active and not st.session_state.game_over else "🔴 GESTOPT"
        if st.session_state.game_over:
            status = "💀 GAME OVER"
        
        st.markdown(f"""
        <div class="game-stats">
        <h3>Status</h3>
        <h2>{status}</h2>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Info
        st.markdown("### ℹ️ Scoring")
        st.markdown("""
        - **+10 punten** per ontweek object
        - **Level up** elke 100 punten
        - **Snelheid** neemt toe met level
        - **Game over** bij 1 hit
        """)
        
        st.markdown("### 🎯 Pro Tips")
        st.markdown("""
        - Blijf in beweging
        - Anticipeer op objecten
        - Goede verlichting helpt
        - Blijf binnen camera bereik
        - Volledige bewegingen maken
        """)
        
        st.markdown("### 🏋️ Bewegingen")
        st.markdown("""
        - **Hoog (⬆️)**: Spring omhoog
        - **Midden (➡️)**: Buig voorover
        - **Laag (⬇️)**: Hurk of lig
        """)

if __name__ == "__main__":
    main()
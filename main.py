import pygame
import sys
from track_generator import generate_track
from car import Car
from ux import GameUX
from ai_opponent import AIOpponent

def main():
    """
    Main entry point for the top-down racing game.
    Initializes pygame, generates track, creates cars, and runs game loop.
    """
    pygame.init()
    
    # Game constants
    SCREEN_WIDTH = 1200
    SCREEN_HEIGHT = 800
    FPS = 60
    
    # Initialize display
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Low-Poly Racing - Chill Vibes")
    clock = pygame.time.Clock()
    
    # Generate procedural track
    print("Generating procedural race track...")
    track_data = generate_track(width=50, complexity=8)
    
    # Create player car with realistic properties
    player_car = Car(
        x=track_data['start_pos'][0],
        y=track_data['start_pos'][1],
        angle=track_data['start_angle'],
        color=(100, 150, 255),  # Cool blue - chill aesthetic
        max_speed=20000.0,
        acceleration=150.0,
        turning_speed=2.5,
        friction=0.92,
        name="Player"
    )
    
    # Create AI opponent
    ai_car = Car(
        x=track_data['start_pos'][0] - 60,
        y=track_data['start_pos'][1],
        angle=track_data['start_angle'],
        color=(255, 150, 100),  # Warm orange
        max_speed=6.5,
        acceleration=0.25,
        turning_speed=3.0,
        friction=0.95,
        name="AI Opponent"
    )
    
    # Initialize AI controller
    ai_opponent = AIOpponent(ai_car, track_data)
    
    # Initialize game UX system
    game_ux = GameUX(screen, track_data, player_car, ai_car)
    
    # Main game loop
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0  # Delta time in seconds
        
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
        
        # Update game state
        game_ux.handle_input()
        player_car.update(dt, track_data)
        
        # Update AI opponent
        ai_opponent.update(dt)
        ai_car.update(dt, track_data)
        
        # Render everything
        game_ux.render()
        
        pygame.display.flip()
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
import pygame
from PIL import Image
from gpiozero import PWMLED
from pygame.surface import Surface
from pygame import image

led = PWMLED(23)
led.value = 1
pygame.display.init()

size = (pygame.display.Info().current_w, pygame.display.Info().current_h)
pygame.mouse.set_visible(False)
screen = pygame.display.set_mode(size, pygame.FULLSCREEN)

        # Clear the screen to start
screen.fill((0, 0, 0))        
        # Initialise font support
pygame.font.init()
        # Render the screen
pygame.display.update()

red = (255, 0, 0)
screen.fill(red)
        # Update the display
pygame.display.update()


font = pygame.font.Font(None, 30)
# Render some white text (pyScope 0.1) onto text_surface
text_surface = font.render('Guckguck!!', 
True, (255, 255, 255))  # White text
# Blit the text at 10, 0
screen.blit(text_surface, (10, 0))
# Update the display
pygame.display.update()


Image.open("../assets/ab67616d0000b273a877db7d95b6045046414e23.jpg").save("../assets/temp.bmp")


picture = pygame.image.load('../assets/temp.bmp')
picture = pygame.transform.scale(picture, (320, 240))
screen.blit(picture, (0, 0))
pygame.display.update()

pygame.image.get_extended()
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
pygame.font.init()
screen = pygame.display.set_mode(size, pygame.FULLSCREEN)

        # Clear the screen to start
screen.fill((0, 0, 0))        
        # Initialise font support

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

WHITE = (255, 255, 255)
GREEN = (0, 255, 0)

Image.open("../assets/ab67616d0000b273a877db7d95b6045046414e23.jpg").save("../assets/temp.bmp")
picture = pygame.image.load('../assets/temp.bmp')
size
psize = picture.get_size()
scale = size[1]/psize[1]
psize_new = tuple(int(s * scale) for s in psize)

picture = pygame.transform.scale(picture, psize_new)
coord = (int((size[0] - psize_new[0]) / 2), int((size[1] - psize_new[1]) / 2))
screen.fill((0, 0, 0))     
screen.blit(picture, coord)
pygame.display.update()

def draw_boxes(n, active, side = 'left',
                basecolor = (255, 255, 255),
                activecolor = (0, 255, 0)):

        X = 10 if side == 'left' else 290
        screen_h = 240
#        n = 10
        box = screen_h / n
        margin = max(int(.1 * box),1)
        h = box - 2 * margin

#       active = 7

        for k in range(n):
                color = basecolor if k >= active else activecolor
                pygame.draw.rect(screen, color, 
                        (X, screen_h - h - margin - box * k,20,h))

def remove_boxes(side = 'left'):
        X = 10 if side == 'left' else 290
        color = (0, 0, 0)
        pygame.draw.rect(screen, color, 
                        (X, 0, 20, 240))                

screen.fill((0, 0, 0))
screen.blit(picture, coord)

n = 25
for k in range(n):
        draw_boxes(n, k + 1, 'left')
        pygame.display.update()
        pygame.time.wait(50)
remove_boxes('left')
pygame.display.update()
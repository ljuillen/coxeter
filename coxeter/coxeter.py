import tqdm
from PIL import Image
from math import sin,cos,tan,sqrt,floor
from cmath import exp

import random
import coxeter

PI = 3.14159265359


# COLOURS
def HTMLColorToRGB(colorstring):
    """ convert #RRGGBB to an (R, G, B) tuple """
    colorstring = colorstring.strip()
    if colorstring[0] == '#': colorstring = colorstring[1:]
    if len(colorstring) != 6:
        raise coxeter.exceptions.ColorFormatError(
            "input #%s is not in #RRGGBB format" %colorstring)
    r, g, b = colorstring[:2], colorstring[2:4], colorstring[4:]
    r, g, b = [int(n, 16) for n in (r, g, b)]
    return (r, g, b, 255)

# geom functions
def abs2(w):
    return w.real**2 + w.imag**2

#bilinear sampling
def lerp(a, b, coord):
    if isinstance(a, tuple):
        return tuple([lerp(c, d, coord) for c,d in zip(a,b)])
    ratio = coord - floor(coord)
    return int(round(a * (1.0-ratio) + b * ratio))

def bilinear(im, x, y):
    x1, y1 = int(floor(x)), int(floor(y))
    x2, y2 = x1+1, y1+1
    left = lerp(im[x1, y1], im[x1, y2], y)
    right = lerp(im[x2, y1], im[x2, y2], y)
    return lerp(left, right, x)


def main(
        p,
        q,
        size,
        input_image,
        half_plane,
        mobius,
        polygon,
        max_iterations,
        zoom,
        translate,
        alternating,
        oversampling):

    if q < 0:#infinity
        q = 2**10

    if (p-2)*(q-2) <= 4:
        raise coxeter.exceptions.NotHyperbolicError(
            "(p - 2) * (q - 2) < 4: tessellation is not hyperbolic")

    if (alternating and p % 2):
        raise coxeter.exceptions.AlternatingModeError(
            "alternating mode cannot be used with odd p.")

    size = size * oversampling
    shape = (size, size)

    #Input sector precalc
    phiangle = PI/2. - (PI/p + PI/q)

    d = sqrt((cos(PI/q)**2) / (cos(PI/q)**2 - sin(PI/p)**2))
    r = sqrt((sin(PI/p)**2) / (cos(PI/q)**2 - sin(PI/p)**2))

    a = cos(phiangle)*r
    x_input_sector = d-a
    y_input_sector = sin(phiangle)*r
    input_sector = max(x_input_sector, y_input_sector)

    out = Image.new("RGB", shape, "white")
    out_pixels = out.load()

    rot2PIp = exp(1j*2*PI/float(p))
    tanPIp = tan(PI/float(p))

    if input_image:
        inimage_pixels = input_image.load()
        inW, inH = input_image.size
        ar,ag,ab = 0,0,0
        count = 0

        for x in range(inW):
            for y in range(inH):
                temp = inimage_pixels[x,y]
                ar+=temp[0]
                ag+=temp[1]
                ab+=temp[2]
                count += 1
        average_colour = (ar // count, ag // count, ab // count)


    if (not alternating):
        rotator = rot2PIp
        curtanPIp = tanPIp
    else:
        rotator = rot2PIp ** 2
        # halfrot = exp(1j*2*PI/float(p))
        # tanPIp = tan(PI/float(p))
        doubletanPIp = tan(2*PI/float(p))
        curtanPIp = doubletanPIp


    centre = complex(d,0) # center of inversion circle
    r2 = r*r

    red = HTMLColorToRGB("#FF3333")
    black = HTMLColorToRGB("#000000")

    def in_fund(z):
        if alternating:
            rot_centre = rot2PIp * centre
            return (
                (z.imag >=0) and
                (z.imag < doubletanPIp * z.real) and
                ((abs2(z-centre) > r2) and ( abs2(z - centre*rot2PIp)> r2)))
        else:
            return (
                (z.imag >= 0) and
                (z.imag < tanPIp * z.real) and
                (abs2(z - centre) > r2 ))



    for x in tqdm.trange(shape[0]):
        for y in range(shape[1]):
            if (half_plane):
                X = 2*float(x)/shape[0]        
                Y = 2*float(shape[1]-y)/shape[1]  
                w = complex(X,Y)
                z = (w-1j)/(-1j*w + 1)
            else:
                # should allow for arbitrary affine maps
                X = (2*float(x)/shape[0]-1. ) 
                Y = (2*float(y)/shape[1]-1. )
                z = translate + complex(X,Y) * zoom

            # exclude if outside the disk
            if (abs2(z)  > 1):
                continue

            #mobius
            if mobius:
                z = (z+mobius)/(1+ z*mobius)

            endflag = False # detect loop
            outflag = False # detect out of disk
            parity = 0      # count transformation parity

            for it in range(max_iterations): 

                # rotate z into fundamental wedge
                while((abs(z.imag) > curtanPIp * z.real)):
                    if (z.imag < 0):
                        z *= rotator
                    else:
                        z /= rotator

                if in_fund(z):
                    break

                # flip
                z = z.conjugate()
                if (not polygon):
                    parity += 1
    
                if in_fund(z):
                    break


                # invert
                local_centre = centre if ((not alternating) or (abs(z.imag) < tanPIp * z.real)) else rot_centre

                w = z - local_centre
                w = w * r2 / abs2(w)
                nz = local_centre + w
                
                if (abs2(nz) < abs2(z)):
                    z = nz    
                    parity += 1

                if in_fund(z):
                    break

                if it == max_iterations - 1:
                    endflag = True

            # produce colour
            if (in_fund(z)):
                if input_image:
                    xx = int(z.real/input_sector*inW)
                    yy = int(z.imag/input_sector*inH)
                    try:
                        c = bilinear(inimage_pixels,xx,yy)
                    except IndexError:
                        c = average_colour #(0,255,255,255)
                else:
                    # c = (int(z.real*255),int(z.imag*255),0,255)
                    c = red if (parity % 2 == 0) else black
            else:
                c = (0,255,0,255) # error?

            if (endflag):
                if input_image:
                    c = average_colour
                else:
                    c = (0,0,255,255) # too many iters

            if (outflag):
                c = (255,0,255,255) # out of circle

            out_pixels[x,y] = c

    if (oversampling > 1):
        out = out.resize(shape, Image.LANCZOS)

    return out
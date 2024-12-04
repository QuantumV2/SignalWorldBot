import discord
from discord.ext import commands
import gzip
import io
import base64
from PIL import Image
import format
import json
from dotenv import load_dotenv
import os
import zlib
import hashlib

load_dotenv()  # take environment variables from .env.
intents = discord.Intents.default()
intents.messages = True  # Enable message intents
intents.message_content = True  # Enable message intents
bot = commands.Bot(command_prefix='sw!', intents=intents)

# Atlas configuration
ATLAS_PATH = "tileset.png"
ATLAS_SIZE = 1024
CELL_SIZE = 128  # Assuming each cell in the atlas is 32x32 pixels


CELL_POSITIONS = {
	-1:(-1,-1),
	0: (0,0),
	1: (1,0),
	2: (2,0),
	3: (3,0),
	4: (0,1),
	5: (1,1),
	6: (2,1),
	7: (3,1),
	8: (0,2),
	9: (1,2),
	10:(2,2),
	11:(5,1),
	12:(5,0),
}

# Load the atlas image
atlas_image = Image.open(ATLAS_PATH)

#{"d":[[[0,0],["(-2, -2)",0,90,0]],[[0,1],["(-2, -1)",0,0,0]],[[0,2],["(-2, 0)",0,0,0]],
# [[1,0],["(-1, -2)",0,90,0]],[[1,2],["(-1, 0)",0,270,0]],[[2,0],["(0, -2)",0,180,0]],
# [[2,1],["(0, -1)",0,180,0]],[[2,2],["(0, 0)",0,270,0]]],"s":[3,3]}
def decode_circuit(encoded_data):
    jsdata = format.BitReader.decompress(encoded_data)
    size = jsdata['s']
    width = size[0]
    height = size[1]
    data = jsdata['d']


    return width, height, data

def get_cell_image(cell_type):
    if cell_type not in CELL_POSITIONS:
        return None
    x, y = CELL_POSITIONS[cell_type]
    x *= 128
    y *= 128
    return atlas_image.crop((x, y, x + CELL_SIZE, y + CELL_SIZE))

def modify_non_transparent_colors(image, power):
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    pixdata = image.load()
    
    for y in range(image.size[1]):
        for x in range(image.size[0]):
            r, g, b, a = pixdata[x, y]
            if a > 0:
                new_r, new_g, new_b = r+255,g+255,b+255
                if power in [1,3]:
                    new_r, new_g, new_b = (r + 255, g, b)
                elif power == 2:
                    new_r, new_g, new_b = (r, g, b +255)
                pixdata[x, y] = (new_r, new_g, new_b, a)
    
    return image
def render_circuit(width, height, grid_data):
    output_cell_size = 50  # Size of cells in the output image
    img = Image.new('RGBA', (width * output_cell_size, height * output_cell_size), color=(255, 255, 255, 0))

    for cell in grid_data:
        cell_type = cell[1][3]
        cell_rot = cell[1][2]
        
        cell_power = cell[1][1]
        cell_pos = cell[0]
        cell_image = get_cell_image(cell_type)
        x = cell_pos[0]
        y = cell_pos[1]
        if cell_image:
            cell_image = modify_non_transparent_colors(cell_image, int(cell_power) )
            cell_image = cell_image.rotate(-cell_rot)
            cell_image = cell_image.resize((output_cell_size, output_cell_size), Image.LANCZOS)
            img.paste(cell_image, (x * output_cell_size, y * output_cell_size), cell_image)

    return img
@bot.command()
async def render(ctx, encoded_circuit):
    loadingmsg = await ctx.reply("Loading... <a:spinning:1313746013533507636>", mention_author=False)
    try:

        # Decode base64 if necessary
        binary_data = base64.b64decode(encoded_circuit)
        # Decompress gzip
        decompressed_data = zlib.decompress(binary_data)
        if len(decompressed_data) > 100000:
            raise ValueError("Data size " + "\"" + str(len(decompressed_data)) + "\"" + " too big to render, sorry :(")

        # Decode the circuit data
        width, height, grid_data = decode_circuit(decompressed_data)

        # Render the circuit
        circuit_image = render_circuit(width, height, grid_data)

        # Save and send the image
        buffer = io.BytesIO()
        circuit_image.save(buffer, format='PNG')
        buffer.seek(0)

        await ctx.reply(f"Finished rendering circuit {hashlib.md5(decompressed_data).hexdigest()}, {width}x{height}",  file=discord.File(buffer, filename='circuit.png'))
    except Exception as e:
        await ctx.reply(f"Error rendering circuit: {str(e)}")
    await loadingmsg.delete()


def render_noncommand(encoded_circuit):
    # Decode base64 if necessary
    binary_data = base64.b64decode(encoded_circuit)
    # Decompress gzip
    decompressed_data = zlib.decompress(binary_data)

    # Decode the circuit data
    width, height, grid_data = decode_circuit(decompressed_data)

    # Render the circuit
    circuit_image = render_circuit(width, height, grid_data)

    # Save and send the image
    buffer = io.BytesIO()
    circuit_image.show(buffer)
    buffer.seek(0)
#render_noncommand("eJztWj9v1UAMd6wWRYCipEJFostr1YGqS54ELIihA0jMVOqIOlSIoVPZgIWFD4AYGJgYGNn4MHwafOe7e/cvl0te8lok1MiKHJ/P/tlnO3l9dQbFn+J3Ae8uDvcR6M+jW7AV5d+CWzE+7uGeWVVCae5ZXlIlk6PTWrXT7DQ1iHtN8Q7e+Sc5lcPZxu3E06f4lO4FHjeeLkpJK0HZZrL/GT6j+xZa8usu3PX4lCE33zvP2ofwUPlSRp4+gkc2Agut4QRPjMwhHCqvNWJ0Rjy60uDer2Qs/YtanhdIUrlKUclpAC/wwrNqB3aIkgzRGmo6fffgXq8kcaIyFVRefHPkDWdymVWWhtgOxTNJG727QWCT+3qYcB2metKUwh7PtoSMp4f5XRq8p95aH4HA00bTLv0jNERxoAxUklUPGlFJTyfVAZbZL3viwtrCvUZo6LKB6G24nbNXKPlfZ/455e7cu+8k2jx/TU6ynkLqLGBFe3EYoSFig/ZFnBSn8iT3zVhFe73BN7VlIVROBzE0nDcWMWy7bLOmkbl2YV+UzJajWTy10EjbyRqaLSdSmRpU7GTfb2Vke3cUUZPyywx50n+O560VU8dTK/+N/ZTtXR7xXLG0M8SWsSqkrS0iqW37VdDlzCClFfMuTkhdGfIeqixK05ODvZzuW8apEjaae85HH3spv7Tkl7ojyXqm/ON3hhh9Ak/abs/YRuMf29jqc8uR8KqDobRW1Q65lu1dqu47EvduTj7iwg+NO6OZg7iRXAPrF/DCQ/AADpK45HuV43Pac7/G6YjbTz2d0I2O3zl0DjBe/JQzZJUnvQjifby/4ZyxkQvxExWpUufwATxw+NwlK/xR0JXIik8FXeTbt4KuDVei0Lt8H+n0D/DuS0HXYF9COtyXuTwK49UXi3XilfbuZvk4Lm8t33s93Zy/wyOYXiX6y/X4yLX+A3wgP9/j+/Ym2VJeoy1o+tvQWjQ1PYVTwuMKr0YiAau+o5CAEUjQLNOCmkhRTwAJSjOMiYH4ulbBLuySHx/xYxO8O14XrWMzR5qOWzVQA/4s6GqDqjEVp5b7RPK7VNmTn2d+nEHF+XtB10we8DcBnpjzM5JPxAIWbj3ArwVd4dvOVByDtXmHmLVaJCaF2p3XQ86gN4e8tZwH6jcPTUW29HE4xvQ3oN6BjC6E0bW/2NjfJRIcO3LCirzsCjoPXuKl9+WHnoacMIpN1xl1T+omc2iSN87uvOFYNUGVnorjxHNk/xTxVJrtd9cpOF7MeyLfl49BXcbPBV0z2R49LXNUuBEVa+Aq8e3ViwNFns9qXh/E1/h6yd89YhR1D1NYlZ09bNWxAN/iWwdVKwvSbyDpVWHGbWzqXbtTCUwSOPP0WkOdiJ3sGvgSXzpfLK2sXosDEWzF1BKLeFBvRBa1/E7UQZXkdfQAOyKWvLR5YAZm5W1QAcKzGY2yRFXEN4Gk6dkUF/PlU1VQwDM8G+zRKK+NR5wzBucJo9lxjlTshKcZKHmzi4U2PsbHLawwnBYfgxLjI3Yp1UxtTnGv/amJagKEpQ1r1+R8NEBXmOAUyFik0dBrZebjEpeTW95VN2aIAj7H5wl/xX8dVXiERzOd5WidpB2P8bjHKpjFqmTdTlslfk2Z0J5kH/kL0mozlQ==")
bot.run(os.getenv("TOKEN"))

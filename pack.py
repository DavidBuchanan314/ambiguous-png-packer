import zlib
from io import BytesIO
from PIL import Image
import sys

def decompress_headerless(data):
	d = zlib.decompressobj(wbits=-15)
	result = d.decompress(data)
	result += d.flush()

	# do all the checks we can?
	assert(len(d.unconsumed_tail) == 0)
	assert(len(d.unused_data) == 0)

	return result

def compress(data):
	c = zlib.compressobj(level=9, wbits=-15)
	result = c.compress(data)
	result += c.flush(zlib.Z_FULL_FLUSH)
	return result

def verbatim(data, last=False):
	result = b"\x01" if last else b"\x00"
	result += len(data).to_bytes(2, "little")
	result += (len(data)^0xffff).to_bytes(2, "little")
	return result + data

def compress_to_size(data, size):
	for i in range(1, len(data)):
		attempt = verbatim(b"") + compress(data[:-i]) + verbatim(data[-i:])
		remainder = size - len(attempt)
		if remainder % 5 == 0:
			break
	else:
		return False

	if remainder < 0:
		return False
	attempt += verbatim(b"") * (remainder // 5)
	assert(len(attempt) == size)
	assert(decompress_headerless(attempt) == data)
	return attempt

def apply_filter(im):
	width, _ = im.size
	imgbytes = im.tobytes()
	filtered = b""
	stride = width * 3
	for i in range(0, len(imgbytes), stride):
		filtered += b"\x00" + imgbytes[i:i + stride]
	return filtered

def check_filter_bytes(data, width):
	stride = width * 3 + 1
	for i in range(0, len(data), stride):
		if data[i] != 0:
			print(data[i-10:i+10].hex())
			raise Exception(f"BAD FILTER AT OFFSET {i}")

def adler32(msg, init=1):
	a = init & 0xffff
	b = init >> 16
	for c in msg:
		a = (a + c) % 65521
		b = (b + a) % 65521
	return a | (b << 16)

def write_png_chunk(stream, name, body):
	stream.write(len(body).to_bytes(4, "big"))
	stream.write(name)
	stream.write(body)
	crc = zlib.crc32(body, zlib.crc32(name))
	stream.write(crc.to_bytes(4, "big"))

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

def main(applepath, worldpath, outpath):
	appleimg = Image.open(applepath).convert("RGB")
	width, height = appleimg.size
	worldimg = Image.open(worldpath).convert("RGB")
	width2, height2 = worldimg.size

	if width != width2 or height != height2:
		raise Exception("Input images must be the same size!")

	TARGET_SIZE = (width*3) + 1

	MSG1 = apply_filter(appleimg)
	MSG2 = apply_filter(worldimg)

	a = b""
	a += verbatim(bytes(TARGET_SIZE)) # row of empty pixels
	a += verbatim(bytes(TARGET_SIZE))[:5] # start the zlib desync

	b = b""

	ypos = 0

	while ypos < height:
		for pieceheight in range(2, height-ypos): # TODO: binary search
			start = TARGET_SIZE*ypos
			end = TARGET_SIZE*(ypos+pieceheight)
			acomp = compress_to_size(MSG1[start:end], TARGET_SIZE-5)
			if not acomp:
				break
			bcomp = compress_to_size(MSG2[start:end], TARGET_SIZE-5)
			if not bcomp:
				break
		else:
			pieceheight += 1
		pieceheight -= 1

		start = TARGET_SIZE*ypos
		end = TARGET_SIZE*(ypos+pieceheight)
		acomp = compress_to_size(MSG1[start:end], TARGET_SIZE-5)
		bcomp = compress_to_size(MSG2[start:end], TARGET_SIZE-5)
		
		if (acomp is False) or (bcomp is False):
			raise Exception("unable to compress to exact size")

		b += acomp
		b += verbatim(bytes(TARGET_SIZE))[:5]
		b += bcomp
		b += verbatim(bytes(TARGET_SIZE))[:5]

		ypos += pieceheight + 1

	# re-sync the zlib streams
	b = b[:-5]
	b += verbatim(b"")
	b += verbatim(b"", last=True)

	interp_1 = decompress_headerless(a) + decompress_headerless(b)
	interp_2 = decompress_headerless(a + b)

	check_filter_bytes(interp_1, width)
	check_filter_bytes(interp_2, width)

	a = b"\x78\xda" + a
	b = b + adler32(interp_2).to_bytes(4, "big")

	height = ypos + 1
	outfile = open(outpath, "wb")

	outfile.write(PNG_MAGIC)

	ihdr = b""
	ihdr += width.to_bytes(4, "big")
	ihdr += height.to_bytes(4, "big")
	ihdr += (8).to_bytes(1, "big") # bitdepth
	ihdr += (2).to_bytes(1, "big") # true colour
	ihdr += (0).to_bytes(1, "big") # compression method
	ihdr += (0).to_bytes(1, "big") # filter method
	ihdr += (0).to_bytes(1, "big") # interlace method

	write_png_chunk(outfile, b"IHDR", ihdr)

	idat_chunks = BytesIO()
	write_png_chunk(idat_chunks, b"IDAT", a)
	first_offset = idat_chunks.tell()
	write_png_chunk(idat_chunks, b"IDAT", b)

	n = 2
	idot_size = 24 + 8 * n

	idot = b""
	idot += n.to_bytes(4, "big") # height divisor
	idot += (0).to_bytes(4, "big") # unknown
	idot += (1).to_bytes(4, "big") # divided height
	idot += (idot_size).to_bytes(4, "big") # unknown
	idot += (1).to_bytes(4, "big") # first height
	idot += (height-1).to_bytes(4, "big") # second height
	idot += (idot_size + first_offset).to_bytes(4, "big") # idat restart offset

	write_png_chunk(outfile, b"iDOT", idot)

	idat_chunks.seek(0)
	outfile.write(idat_chunks.read())

	write_png_chunk(outfile, b"IEND", b"")
	outfile.close()

if __name__ == "__main__":
	if len(sys.argv) != 4:
		print(f"USAGE: {sys.argv[0]} apple_input.png other_input.png output.png")
		exit()
	main(*sys.argv[1:4])

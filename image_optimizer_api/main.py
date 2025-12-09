# Required imports
from fastapi import FastAPI, File, UploadFile, Query, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image
import io # For in-memory byte manipulation
from typing import Optional # Used for Query parameters that can be None

app = FastAPI(
    title="Image Optimizer API",
    description="API for image conversion and optimization using Pillow and FastAPI.",
    version="1.0.0"
)

# Test Route
@app.get("/")
def read_root():
    return {"message": "Image Optimizer API is running!"}

# --- CONVERSION ENDPOINT ---
@app.post(
    "/api/v1/convert",
    summary="Converts and Optimizes an Image to a New Format (e.g., WebP, JPEG)",
    response_description="The optimized image file."
)
async def convert_image(
    file: UploadFile = File(..., description="Image file to be converted (JPEG, PNG, etc)."),
    target_format: str = Query(
        "webp", 
        description="The desired output format (e.g., webp, jpeg, png).",
        min_length=3,
        max_length=4
    ),
    quality: int = Query(
        85, 
        description="The compression quality (0 to 100). Only used for lossy formats (JPEG, WebP).",
        ge=1, 
        le=100
    )
):
    # 1. Simple Format Validation
    # We use upper() because the Pillow library uses uppercase format names (e.g., "WEBP")
    target_format = target_format.upper()
    if target_format not in ["WEBP", "JPEG", "PNG", "BMP"]:
         raise HTTPException(
             status_code=400, 
             detail=f"Output format '{target_format}' is not supported."
         )

    # 2. Reading the File In-Memory
    # This is essential for maintaining performance and security.
    try:
        contents = await file.read()
        img_stream = io.BytesIO(contents)
        img = Image.open(img_stream)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not process the image. Error: {e}")

    # 3. Processing and Optimization
    output_stream = io.BytesIO()
    
    try:
        # Compression (quality) is only passed for lossy formats
        if target_format in ["JPEG", "WEBP"]:
            img.save(output_stream, format=target_format, quality=quality)
        else:
            img.save(output_stream, format=target_format)
            
        output_stream.seek(0) # Rewind the buffer for reading
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to save the image in the new format. Error: {e}"
        )

    # 4. Returning the Optimized Image
    # Defines the correct Content-Type for the browser
    media_type = f"image/{target_format.lower()}"
    filename = f"optimized.{target_format.lower()}"
    
    return StreamingResponse(
        output_stream,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# --- RESIZE ENDPOINT ---
@app.post(
    "/api/v1/resize",
    summary="Resizes an Image to a Specific Width and/or Height",
    response_description="The resized and optimized image file."
)
async def resize_image(
    file: UploadFile = File(..., description="Image file to be resized."),
    width: Optional[int] = Query(None, description="New desired width in pixels. If omitted, it will be calculated to maintain the aspect ratio."),
    height: Optional[int] = Query(None, description="New desired height in pixels. If omitted, it will be calculated to maintain the aspect ratio."),
    quality: int = Query(
        85, 
        description="The compression quality (0 to 100). Used for lossy formats (JPEG, WebP).",
        ge=1, 
        le=100
    )
):
    # 1. Parameter Validation
    if width is None and height is None:
        raise HTTPException(
            status_code=400, 
            detail="At least 'width' or 'height' must be provided for resizing."
        )

    # 2. Reading the File In-Memory
    try:
        contents = await file.read()
        img_stream = io.BytesIO(contents)
        img = Image.open(img_stream)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not process the image. Error: {e}")

    original_width, original_height = img.size
    
    # 3. Aspect Ratio Calculation
    
    # If only width was provided
    if width is not None and height is None:
        # Formula: new_height = (new_width / original_width) * original_height
        height = int((width / original_width) * original_height)
    
    # If only height was provided
    elif height is not None and width is None:
        # Formula: new_width = (new_height / original_height) * original_width
        width = int((height / original_height) * original_width)
    
    # If both are provided, resize to the exact size (may distort the image)
    # We could add a 'crop' logic here in the future, but for now we use the exact size.

    # 4. Resizing with Pillow
    try:
        # Uses the Image.resize method with the Lanczos filter for better quality
        resized_img = img.resize((width, height), Image.Resampling.LANCZOS)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resize the image. Error: {e}")

    # 5. Optimization and Return
    output_stream = io.BytesIO()
    
    # Detects the original format for saving
    # If the original format is unknown (img.format is None), we use JPEG as a fallback.
    original_format = img.format if img.format else "JPEG"
    
    try:
        # Saves with quality for lossy formats (JPEG, WebP)
        if original_format in ["JPEG", "WEBP"]:
            resized_img.save(output_stream, format=original_format, quality=quality)
        else:
            resized_img.save(output_stream, format=original_format)
            
        output_stream.seek(0)
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to save the resized image. Error: {e}"
        )

    # Returning the Optimized Image
    media_type = f"image/{original_format.lower()}"
    filename = f"resized_{width}x{height}.{original_format.lower()}"
    
    return StreamingResponse(
        output_stream,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
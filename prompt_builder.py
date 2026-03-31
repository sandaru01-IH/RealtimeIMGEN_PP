IMG2IMG_NEGATIVE = (
    "ugly, blurry, low quality, cartoon, deformed, distorted, "
    "watermark, text, signature, oversaturated, different buildings, "
    "different road, different perspective, completely different scene"
)

TXT2IMG_NEGATIVE = (
    "cars, traffic, pollution, ugly, blurry, low quality, cartoon, "
    "deformed, distorted, watermark, text, signature, oversaturated"
)


def build_prompt(top_words: list[str], img2img: bool = False) -> tuple[str, str]:
    """
    Returns (positive_prompt, negative_prompt).
    img2img=True uses an additive prompt that preserves the base photo.
    img2img=False uses a generative prompt for txt2img mode.
    """
    words = top_words[:8]

    if img2img:
        # Additive language: tell the model to keep the scene and layer in elements
        if not words:
            return "", ""  # No words yet — caller should skip generation

        feature_str = ", ".join(words)
        positive = (
            f"The same street scene with {feature_str} added, "
            "same buildings, same road, same perspective, same sky, "
            "same camera angle, photorealistic, urban design elements layered in, "
            "highly detailed, professional architecture photography"
        )
        return positive, IMG2IMG_NEGATIVE

    else:
        # Generative txt2img — build from scratch
        if not words:
            feature_str = "green spaces, pedestrian paths, trees, benches, open plazas"
        else:
            feature_str = ", ".join(words)

        positive = (
            f"A photorealistic urban street redesigned with {feature_str}, "
            "wide angle view, golden hour lighting, architectural visualization, "
            "people walking, vibrant community space, lush vegetation, "
            "modern sustainable design, highly detailed, 8k resolution, "
            "professional photography, sharp focus, urban planning render"
        )
        return positive, TXT2IMG_NEGATIVE

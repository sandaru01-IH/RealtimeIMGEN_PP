NEGATIVE_PROMPT = (
    "cars, traffic, pollution, ugly, blurry, low quality, cartoon, "
    "deformed, distorted, watermark, text, signature, oversaturated"
)


def build_prompt(top_words: list[str]) -> tuple[str, str]:
    """
    Takes up to 8 top words and returns (positive_prompt, negative_prompt).
    """
    words = top_words[:8]

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

    return positive, NEGATIVE_PROMPT

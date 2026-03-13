from setuptools import setup, find_packages

setup(
    name="faceid",
    version="0.1.0",
    description="Sistema locale di face recognition (InsightFace + FAISS).",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "opencv-python",
        "insightface",
        "onnxruntime",
        "faiss-cpu",
        "numpy",
    ],
    entry_points={
        "console_scripts": [
            "faceid=faceid.cli:main",
        ],
    },
)

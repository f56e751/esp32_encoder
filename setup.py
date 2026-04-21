from setuptools import setup

package_name = "esp32_encoder"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="minu",
    maintainer_email="fortriver54321@gmail.com",
    description=(
        "ESP32 conveyor belt encoder bridge. Reads CSV over serial and "
        "publishes conveyor speed/distance."
    ),
    license="MIT",
    entry_points={
        "console_scripts": [
            "conveyor_node = esp32_encoder.conveyor_node:main",
        ],
    },
)

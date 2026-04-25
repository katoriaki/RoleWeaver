import shlex
import subprocess
from pathlib import Path
from typing import Optional


def convert_to_silk_if_configured(audio_path: Path, command_template: Optional[str]) -> Path:
    if not command_template:
        return audio_path

    output_path = audio_path.with_suffix(".silk")
    command = command_template.format(
        input=str(audio_path),
        output=str(output_path),
    )
    subprocess.run(shlex.split(command), check=True)
    if not output_path.exists():
        raise RuntimeError(f"Silk converter did not create output file: {output_path}")
    return output_path

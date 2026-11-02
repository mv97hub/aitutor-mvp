"""Seed courses. Quest codes match the curriculum blueprint."""

from app.curriculum.geometry import geometry_course
from app.curriculum.macro import macro_course
from app.curriculum.rome import rome_course

COURSES = [rome_course(), geometry_course(), macro_course()]

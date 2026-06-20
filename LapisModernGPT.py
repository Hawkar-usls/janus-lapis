#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JANUS-LAPIS / LapisModernGPT v0.1.5 Birth-Gate Edition

The alchemists were not fools. They lacked instruments.
We do not worship symbols. We test functions.

v0.1.1: archetype map.
v0.1.2: diversity lock.
v0.1.3: Demiurge layer.
v0.1.4: Canvas / Stagekeeper layer.
v0.1.5: Birth-Gate decision chain.

Core idea:
The philosopher's stone is not only a material.
The stone is also the gate that decides whether a hypothesis is ready to be born.

Boundary:
- No literal transmutation claim.
- No elixir claim.
- No hazardous synthesis protocol.
- No certified material claim.
- No instructions for dangerous chemistry.
- Outputs are computational research vectors and expert-review requests.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple
import argparse, csv, hashlib, json, random, shutil, statistics, zipfile, os, sys

VERSION = "0.1.5-janus-lapis-birth-gate"
DEFAULT_OUTDIR = "janus_lapis_runs"

MATERIAL_FEATURES = [
    "transformation", "purification", "self_healing", "structure_strength", "durability",
    "bio_safety", "energy_conversion", "biomineralization", "accessibility", "testability", "low_hazard"
]

META_FEATURES = [
    "rule_rewriting", "autocatalysis", "closed_loop_learning", "generativity",
    "programmability", "world_modeling", "agency", "feedback_gain"
]

CANVAS_FEATURES = [
    "noise_removal", "surface_readiness", "signal_clarity",
    "safe_containment", "scene_preparation", "creative_potential"
]

GATE_FEATURES = [
    "material_score", "canvas_score", "stagekeeper_score", "demiurge_score",
    "scene_viability", "birth_readiness", "containment_integrity",
    "hypothesis_visibility", "expert_gate", "final_priority"
]

FEATURES = MATERIAL_FEATURES + META_FEATURES + CANVAS_FEATURES

BANNED_TOKENS = {
    "MERCURY","QUICKSILVER","LEAD","ARSENIC","CADMIUM","THALLIUM","URANIUM","PLUTONIUM",
    "AQUA_REGIA","AQUA_FORTIS","CYANIDE","DICHROMATE","CHROMATE","PERCHLORATE","AZIDE",
    "HYDROFLUORIC_ACID","CONCENTRATED_NITRIC_ACID","PHOSGENE","MUSTARD","TOXIC_GAS",
    "EXPLOSIVE","ENERGETIC_MATERIAL","RADIOACTIVE_SOURCE","AMALGAM","DIMETHYLMERCURY",
    "PIRANHA_SOLUTION","WHITE_PHOSPHORUS","CHLORINE_GAS","FLUORINE_GAS"
}

TARGETS = {
    "LAPIS_UNIVERSAL": {
        "transformation":0.14, "purification":0.13, "self_healing":0.11, "structure_strength":0.10,
        "durability":0.10, "bio_safety":0.08, "energy_conversion":0.07, "biomineralization":0.05,
        "rule_rewriting":0.06, "closed_loop_learning":0.06, "generativity":0.04,
        "accessibility":0.02, "testability":0.02, "low_hazard":0.02,
    },
    "LAPIS_CATALYST": {
        "transformation":0.32, "energy_conversion":0.17, "purification":0.13, "durability":0.09,
        "bio_safety":0.07, "testability":0.06, "structure_strength":0.04, "accessibility":0.03,
        "low_hazard":0.04, "generativity":0.03, "feedback_gain":0.02,
    },
    "LAPIS_PURIFIER": {
        "purification":0.34, "transformation":0.14, "durability":0.10, "bio_safety":0.10,
        "structure_strength":0.08, "testability":0.06, "accessibility":0.05, "low_hazard":0.04,
        "self_healing":0.03, "energy_conversion":0.02, "closed_loop_learning":0.04,
    },
    "LAPIS_HEALER": {
        "self_healing":0.31, "bio_safety":0.17, "durability":0.11, "structure_strength":0.10,
        "purification":0.07, "biomineralization":0.07, "testability":0.05, "accessibility":0.04,
        "closed_loop_learning":0.04, "low_hazard":0.02, "feedback_gain":0.02,
    },
    "LAPIS_STONE": {
        "structure_strength":0.25, "durability":0.20, "purification":0.10, "transformation":0.08,
        "bio_safety":0.07, "low_hazard":0.06, "testability":0.05, "accessibility":0.04,
        "biomineralization":0.05, "self_healing":0.03, "world_modeling":0.04, "rule_rewriting":0.03,
    },
    "LAPIS_LIFE": {
        "bio_safety":0.22, "self_healing":0.17, "biomineralization":0.14, "purification":0.10,
        "durability":0.08, "structure_strength":0.07, "transformation":0.05, "testability":0.04,
        "closed_loop_learning":0.05, "feedback_gain":0.04, "accessibility":0.03, "low_hazard":0.01,
    },
    "LAPIS_ENERGY": {
        "energy_conversion":0.32, "transformation":0.20, "durability":0.09, "purification":0.08,
        "structure_strength":0.06, "testability":0.06, "bio_safety":0.05, "accessibility":0.04,
        "generativity":0.04, "feedback_gain":0.03, "low_hazard":0.02, "self_healing":0.01,
    },
    "LAPIS_BIOMINERAL": {
        "biomineralization":0.28, "structure_strength":0.15, "durability":0.13, "bio_safety":0.12,
        "self_healing":0.08, "purification":0.07, "transformation":0.04, "testability":0.03,
        "world_modeling":0.04, "closed_loop_learning":0.03, "accessibility":0.02, "low_hazard":0.01,
    },
    "LAPIS_LOWHAZARD": {
        "low_hazard":0.20, "bio_safety":0.17, "accessibility":0.11, "testability":0.10,
        "purification":0.09, "durability":0.08, "structure_strength":0.06, "self_healing":0.05,
        "closed_loop_learning":0.05, "world_modeling":0.04, "transformation":0.03, "biomineralization":0.02,
    },
    "LAPIS_CANVAS": {
        "noise_removal":0.18, "surface_readiness":0.17, "signal_clarity":0.15,
        "safe_containment":0.14, "scene_preparation":0.14, "creative_potential":0.09,
        "purification":0.05, "durability":0.03, "low_hazard":0.03, "testability":0.02,
    },
    "LAPIS_STAGEKEEPER": {
        "safe_containment":0.20, "scene_preparation":0.18, "surface_readiness":0.14,
        "signal_clarity":0.12, "noise_removal":0.12, "durability":0.08,
        "low_hazard":0.07, "testability":0.04, "creative_potential":0.03, "closed_loop_learning":0.02,
    },
    "LAPIS_DEMIURGE": {
        "rule_rewriting":0.18, "closed_loop_learning":0.17, "generativity":0.15,
        "programmability":0.13, "world_modeling":0.12, "agency":0.10,
        "feedback_gain":0.08, "autocatalysis":0.05, "testability":0.02,
    },
    "LAPIS_WORLD_REWRITER": {
        "rule_rewriting":0.25, "agency":0.15, "world_modeling":0.15,
        "generativity":0.13, "closed_loop_learning":0.12, "programmability":0.10,
        "feedback_gain":0.06, "autocatalysis":0.03, "testability":0.01,
    },
}

ARCHETYPE_DESCRIPTIONS = {
    "LAPIS_UNIVERSAL": "balanced modern philosopher-stone analogue",
    "LAPIS_CATALYST": "stone as transformer: catalysis/resource conversion",
    "LAPIS_PURIFIER": "stone as purifier: adsorption/separation/detox",
    "LAPIS_HEALER": "stone as healer: self-repair/damage recovery/biocompatibility",
    "LAPIS_STONE": "stone as body: durable structured matter",
    "LAPIS_LIFE": "stone as life-compatible matter: biological interface",
    "LAPIS_ENERGY": "stone as spiritus: light/charge/energy conversion",
    "LAPIS_BIOMINERAL": "stone grown from life: biomineral/living fabrication",
    "LAPIS_LOWHAZARD": "stone as safe path: non-toxic, accessible, testable",
    "LAPIS_CANVAS": "stone as clean canvas: purified surface and low-noise field where new order can appear",
    "LAPIS_STAGEKEEPER": "stone as stagekeeper: safe containment and stable scene preparation",
    "LAPIS_DEMIURGE": "stone as engine: self-improving discovery loop that changes the search space",
    "LAPIS_WORLD_REWRITER": "stone as world-rewriter: rule-editing generative system, not a passive material",
}

@dataclass(frozen=True)
class Primitive:
    code: str
    family: str
    role: str
    notes: str

    transformation: float = 0.0
    purification: float = 0.0
    self_healing: float = 0.0
    structure_strength: float = 0.0
    durability: float = 0.0
    bio_safety: float = 0.0
    energy_conversion: float = 0.0
    biomineralization: float = 0.0
    accessibility: float = 0.0
    testability: float = 0.0
    low_hazard: float = 0.0

    rule_rewriting: float = 0.0
    autocatalysis: float = 0.0
    closed_loop_learning: float = 0.0
    generativity: float = 0.0
    programmability: float = 0.0
    world_modeling: float = 0.0
    agency: float = 0.0
    feedback_gain: float = 0.0

    noise_removal: float = 0.0
    surface_readiness: float = 0.0
    signal_clarity: float = 0.0
    safe_containment: float = 0.0
    scene_preparation: float = 0.0
    creative_potential: float = 0.0

    density: float = 1.0

def P(code, family, role, notes, **kw):
    return Primitive(code=code, family=family, role=role, notes=notes, **kw)

PRIMITIVES: List[Primitive] = [
    P("BACTERIAL_CELLULOSE_MATRIX","biopolymer","matrix","nanofibrillar body; modern prima materia",transformation=.20,purification=.25,self_healing=.45,structure_strength=.70,durability=.45,bio_safety=.95,energy_conversion=.08,biomineralization=.35,accessibility=.78,testability=.72,low_hazard=.95,density=1.35),
    P("CHITOSAN_BINDER","biopolymer","binder","cationic film former; adsorption and binding",transformation=.22,purification=.58,self_healing=.45,structure_strength=.55,durability=.48,bio_safety=.86,energy_conversion=.06,biomineralization=.20,accessibility=.65,testability=.72,low_hazard=.88,density=1.42),
    P("ALGINATE_HYDROGEL","biopolymer","hydrogel","ionic hydrogel network; repair/water structure",transformation=.15,purification=.28,self_healing=.70,structure_strength=.36,durability=.35,bio_safety=.92,energy_conversion=.03,biomineralization=.26,accessibility=.72,testability=.75,low_hazard=.90,density=1.60),
    P("PVA_FILM","polymer","binder","film-former and toughening comparison polymer",transformation=.12,purification=.18,self_healing=.62,structure_strength=.45,durability=.42,bio_safety=.80,energy_conversion=.03,biomineralization=.04,accessibility=.82,testability=.75,low_hazard=.82,density=1.19),
    P("GELATIN_COLLAGEN_TOKEN","biopolymer","binder","biopolymer healing/adhesion direction",transformation=.12,purification=.18,self_healing=.66,structure_strength=.40,durability=.35,bio_safety=.82,energy_conversion=.02,biomineralization=.18,accessibility=.70,testability=.70,low_hazard=.82,density=1.30),
    P("TANNIC_ACID_POLYPHENOL","bioactive","crosslinker","complexation, adhesion, antioxidant concept",transformation=.36,purification=.48,self_healing=.48,structure_strength=.36,durability=.42,bio_safety=.78,energy_conversion=.08,biomineralization=.08,accessibility=.60,testability=.62,low_hazard=.78,density=1.50),
    P("CITRIC_ACID_SAFE_TOKEN","modifier","weak_acid","safe weak-acid modifier concept, not protocol",transformation=.25,purification=.18,self_healing=.28,structure_strength=.22,durability=.32,bio_safety=.90,energy_conversion=.02,biomineralization=.06,accessibility=.95,testability=.78,low_hazard=.92,density=1.66),
    P("GLYCEROL_SAFE_TOKEN","modifier","plasticizer","flexibility/toughness modifier token",transformation=.08,purification=.12,self_healing=.50,structure_strength=.05,durability=.20,bio_safety=.92,energy_conversion=.01,biomineralization=.02,accessibility=.95,testability=.80,low_hazard=.92,density=1.26),

    P("SILICA_BIOSILICA_SAFE","mineral","mineral","mineral skeleton; thermal/barrier stability",transformation=.18,purification=.28,self_healing=.08,structure_strength=.78,durability=.86,bio_safety=.84,energy_conversion=.03,biomineralization=.22,accessibility=.86,testability=.72,low_hazard=.86,density=2.20),
    P("CLAY_PLATELET_BARRIER","mineral","platelet","layered tortuous barrier mineral",transformation=.16,purification=.56,self_healing=.12,structure_strength=.62,durability=.76,bio_safety=.82,energy_conversion=.04,biomineralization=.06,accessibility=.92,testability=.76,low_hazard=.84,density=2.35),
    P("ZEOLITE_SAFE","mineral","sorbent","porous sorbent/catalyst support",transformation=.46,purification=.82,self_healing=.05,structure_strength=.52,durability=.74,bio_safety=.80,energy_conversion=.08,biomineralization=.02,accessibility=.78,testability=.78,low_hazard=.82,density=2.10),
    P("HYDROXYAPATITE_SAFE","biomineral","biomineral","bone-like calcium phosphate material",transformation=.20,purification=.46,self_healing=.16,structure_strength=.58,durability=.70,bio_safety=.88,energy_conversion=.03,biomineralization=.72,accessibility=.68,testability=.75,low_hazard=.88,density=3.10),
    P("CALCIUM_CARBONATE_BIOMINERAL","biomineral","biomineral","shell/stone biomineral analogue",transformation=.16,purification=.30,self_healing=.12,structure_strength=.56,durability=.66,bio_safety=.88,energy_conversion=.02,biomineralization=.82,accessibility=.90,testability=.78,low_hazard=.90,density=2.70),
    P("MAGNESIUM_PHOSPHATE_SAFE","biomineral","biomineral","biocement/stone-like safe mineral direction",transformation=.18,purification=.34,self_healing=.10,structure_strength=.60,durability=.72,bio_safety=.84,energy_conversion=.02,biomineralization=.70,accessibility=.68,testability=.70,low_hazard=.84,density=2.70),

    P("BIOCHAR_SAFE","carbon","sorbent","porous carbon adsorption; safe handling assumed",transformation=.42,purification=.78,self_healing=.06,structure_strength=.45,durability=.64,bio_safety=.72,energy_conversion=.22,biomineralization=.04,accessibility=.85,testability=.75,low_hazard=.75,density=1.80),
    P("ACTIVATED_CARBON_SAFE","carbon","sorbent","broad adsorption/purification concept",transformation=.42,purification=.88,self_healing=.04,structure_strength=.42,durability=.62,bio_safety=.76,energy_conversion=.20,biomineralization=.02,accessibility=.88,testability=.80,low_hazard=.78,density=1.80),
    P("BIOBASED_ION_EXCHANGE_TOKEN","sorbent","sorbent","ion exchange / purification concept",transformation=.38,purification=.80,self_healing=.08,structure_strength=.28,durability=.46,bio_safety=.74,energy_conversion=.05,biomineralization=.04,accessibility=.48,testability=.62,low_hazard=.70,density=1.25),

    P("TITANIUM_DIOXIDE_SAFE_TOKEN","photocatalyst","catalyst","photocatalyst concept; not powder protocol",transformation=.78,purification=.56,self_healing=.02,structure_strength=.52,durability=.82,bio_safety=.70,energy_conversion=.70,biomineralization=.02,accessibility=.70,testability=.78,low_hazard=.72,density=4.20),
    P("IRON_OXIDE_SAFE_TOKEN","oxide","catalyst_support","oxide support/magnetic separability concept",transformation=.54,purification=.42,self_healing=.02,structure_strength=.56,durability=.72,bio_safety=.72,energy_conversion=.36,biomineralization=.04,accessibility=.82,testability=.78,low_hazard=.76,density=5.20),
    P("ZINC_OXIDE_SAFE_TOKEN","oxide","catalyst","semiconductor oxide concept; expert review required",transformation=.62,purification=.42,self_healing=.02,structure_strength=.50,durability=.74,bio_safety=.62,energy_conversion=.55,biomineralization=.02,accessibility=.70,testability=.72,low_hazard=.62,density=5.60),
    P("MANGANESE_DIOXIDE_SAFE_TOKEN","oxide","redox_catalyst","redox catalyst concept; expert-only validation",transformation=.70,purification=.48,self_healing=.01,structure_strength=.48,durability=.72,bio_safety=.58,energy_conversion=.42,biomineralization=.02,accessibility=.55,testability=.70,low_hazard=.62,density=5.00),

    P("ENZYME_LACCASE_TOKEN","enzyme","biocatalyst","biocatalytic oxidation concept",transformation=.82,purification=.64,self_healing=.10,structure_strength=.08,durability=.25,bio_safety=.80,energy_conversion=.08,biomineralization=.14,accessibility=.45,testability=.62,low_hazard=.86,density=1.30),
    P("ENZYME_CATALASE_TOKEN","enzyme","biocatalyst","biocatalytic peroxide decomposition concept",transformation=.72,purification=.44,self_healing=.06,structure_strength=.06,durability=.24,bio_safety=.82,energy_conversion=.06,biomineralization=.08,accessibility=.45,testability=.62,low_hazard=.86,density=1.30),
    P("ENZYME_CELLULASE_TOKEN","enzyme","biocatalyst","biopolymer transformation concept; expert review",transformation=.60,purification=.30,self_healing=.08,structure_strength=.04,durability=.18,bio_safety=.78,energy_conversion=.04,biomineralization=.08,accessibility=.42,testability=.55,low_hazard=.82,density=1.30),

    P("PEDOT_PSS_SAFE_TOKEN","conductive_polymer","energy","conductive polymer for charge transport concept",transformation=.44,purification=.18,self_healing=.28,structure_strength=.30,durability=.45,bio_safety=.58,energy_conversion=.72,biomineralization=.02,accessibility=.42,testability=.62,low_hazard=.60,density=1.10),
    P("CARBON_BLACK_SAFE_TOKEN","carbon","energy","conductive carbon concept; safe handling required",transformation=.36,purification=.40,self_healing=.02,structure_strength=.42,durability=.64,bio_safety=.50,energy_conversion=.68,biomineralization=.01,accessibility=.70,testability=.68,low_hazard=.55,density=1.85),
    P("GRAPHENE_OXIDE_SAFE_TOKEN","carbon","advanced","advanced carbon sheet concept; expert-only",transformation=.50,purification=.48,self_healing=.18,structure_strength=.70,durability=.70,bio_safety=.46,energy_conversion=.62,biomineralization=.02,accessibility=.28,testability=.55,low_hazard=.48,density=1.90),
    P("POLYDOPAMINE_SAFE_TOKEN","bioinspired","adhesion","mussel-inspired adhesive/functional coating concept",transformation=.38,purification=.42,self_healing=.56,structure_strength=.42,durability=.50,bio_safety=.66,energy_conversion=.22,biomineralization=.08,accessibility=.36,testability=.54,low_hazard=.62,density=1.30),

    P("BIOMINERALIZATION_MICROBE_TOKEN","bio_process","process","microbial mineralization research direction, expert-only",transformation=.45,purification=.50,self_healing=.42,structure_strength=.50,durability=.52,bio_safety=.70,energy_conversion=.06,biomineralization=.92,accessibility=.36,testability=.48,low_hazard=.68,density=1.20),
    P("MYCELIUM_BINDER_TOKEN","bio_process","binder","fungal/mycelial biofabrication direction",transformation=.28,purification=.36,self_healing=.58,structure_strength=.42,durability=.44,bio_safety=.74,energy_conversion=.04,biomineralization=.68,accessibility=.42,testability=.50,low_hazard=.72,density=.80),
    P("KOMBUCHA_FERMENTATION_TOKEN","bio_process","process","bacterial cellulose growth direction; not protocol",transformation=.25,purification=.28,self_healing=.45,structure_strength=.52,durability=.34,bio_safety=.88,energy_conversion=.03,biomineralization=.58,accessibility=.68,testability=.55,low_hazard=.88,density=1.10),
    P("DIATOM_BIOSILICA_TOKEN","bio_process","biomineral","biological silica architecture concept",transformation=.22,purification=.38,self_healing=.18,structure_strength=.58,durability=.70,bio_safety=.80,energy_conversion=.08,biomineralization=.88,accessibility=.28,testability=.42,low_hazard=.76,density=1.70),

    # Canvas / Stagekeeper layer: safe scene-preparation primitives.
    P("CLEAN_CANVAS_SURFACE","canvas_layer","surface","prepared clean surface / low-noise test field",purification=.62,durability=.50,bio_safety=.86,accessibility=.72,testability=.86,low_hazard=.88,noise_removal=.82,surface_readiness=.94,signal_clarity=.82,safe_containment=.54,scene_preparation=.88,creative_potential=.66,density=1.20),
    P("SIGNAL_CLARITY_GATE","canvas_layer","clarity_gate","removes ambiguity and improves measurable signal",purification=.58,durability=.42,bio_safety=.84,accessibility=.66,testability=.92,low_hazard=.88,noise_removal=.74,surface_readiness=.72,signal_clarity=.96,safe_containment=.50,scene_preparation=.78,creative_potential=.58,density=1.10),
    P("SAFE_CONTAINMENT_MATRIX","canvas_layer","containment","safe boundary that lets experiments be falsifiable",purification=.42,durability=.76,bio_safety=.92,accessibility=.70,testability=.88,low_hazard=.94,noise_removal=.50,surface_readiness=.62,signal_clarity=.66,safe_containment=.96,scene_preparation=.88,creative_potential=.54,density=1.40),
    P("REPRODUCIBLE_SCENE_PROTOCOL","canvas_layer","stage_protocol","repeatable clean scene and measurement protocol",purification=.50,durability=.58,bio_safety=.88,accessibility=.82,testability=.96,low_hazard=.94,noise_removal=.68,surface_readiness=.84,signal_clarity=.86,safe_containment=.82,scene_preparation=.94,creative_potential=.62,density=1.00),
    P("LOW_NOISE_MEMORY_FIELD","canvas_layer","memory_field","keeps failures and context without contaminating new trials",purification=.46,durability=.48,bio_safety=.90,accessibility=.72,testability=.84,low_hazard=.94,noise_removal=.86,surface_readiness=.68,signal_clarity=.88,safe_containment=.66,scene_preparation=.82,creative_potential=.72,closed_loop_learning=.48,world_modeling=.40,density=1.00),
    P("CREATIVE_POTENTIAL_SEED","canvas_layer","creative_seed","prepared blank space that can host new games",purification=.34,durability=.42,bio_safety=.86,accessibility=.74,testability=.74,low_hazard=.92,noise_removal=.46,surface_readiness=.76,signal_clarity=.70,safe_containment=.60,scene_preparation=.88,creative_potential=.98,generativity=.36,density=1.00),

    # Demiurge layer: non-chemical primitives. These represent the discovery engine itself.
    P("GPT_TRANSFORMER_ENGINE","meta_engine","engine","generative transformer for hypothesis creation",testability=.78,low_hazard=.92,rule_rewriting=.72,autocatalysis=.40,closed_loop_learning=.55,generativity=.95,programmability=.88,world_modeling=.74,agency=.52,feedback_gain=.60),
    P("EVOLUTIONARY_SEARCH_LOOP","meta_engine","optimizer","variation-selection search over candidate space",testability=.82,low_hazard=.92,rule_rewriting=.60,autocatalysis=.72,closed_loop_learning=.55,generativity=.74,programmability=.78,world_modeling=.48,agency=.55,feedback_gain=.66),
    P("BAYESIAN_OPTIMIZER","meta_engine","optimizer","surrogate-guided experimental design",testability=.80,low_hazard=.92,rule_rewriting=.55,autocatalysis=.62,closed_loop_learning=.78,generativity=.58,programmability=.74,world_modeling=.72,agency=.48,feedback_gain=.74),
    P("ACTIVE_LEARNING_AUTOLAB","meta_engine","closed_loop","proposes next experiment from measured feedback",testability=.76,low_hazard=.90,rule_rewriting=.66,autocatalysis=.72,closed_loop_learning=.95,generativity=.62,programmability=.72,world_modeling=.76,agency=.62,feedback_gain=.92),
    P("KNOWLEDGE_GRAPH_MEMORY","meta_engine","memory","persistent graph memory of hypotheses/results/failures",testability=.84,low_hazard=.95,rule_rewriting=.52,autocatalysis=.42,closed_loop_learning=.78,generativity=.45,programmability=.70,world_modeling=.88,agency=.38,feedback_gain=.70),
    P("SCORING_FUNCTION_MUTATOR","meta_engine","rule_editor","edits objective functions and constraints",testability=.70,low_hazard=.92,rule_rewriting=.95,autocatalysis=.70,closed_loop_learning=.66,generativity=.68,programmability=.84,world_modeling=.62,agency=.74,feedback_gain=.72),
    P("SIMULATION_SURROGATE_MODEL","meta_engine","world_model","fast surrogate of material behavior",testability=.72,low_hazard=.94,rule_rewriting=.45,autocatalysis=.55,closed_loop_learning=.70,generativity=.40,programmability=.78,world_modeling=.94,agency=.36,feedback_gain=.68),
    P("EXPERT_REVIEW_GATE","meta_engine","safety_gate","human/qualified expert review and falsification gate",testability=.95,low_hazard=.98,rule_rewriting=.38,autocatalysis=.20,closed_loop_learning=.50,generativity=.20,programmability=.60,world_modeling=.58,agency=.25,feedback_gain=.82),
    P("REPOSITORY_PUBLICATION_LOOP","meta_engine","publication","open repo loop: reproducibility, critique, forks",testability=.90,low_hazard=.96,rule_rewriting=.50,autocatalysis=.66,closed_loop_learning=.62,generativity=.48,programmability=.54,world_modeling=.45,agency=.46,feedback_gain=.78),
    P("JANUS_SYMBOLIC_INTERPRETER","meta_engine","interpreter","translation layer between myth, function, and test",testability=.66,low_hazard=.94,rule_rewriting=.84,autocatalysis=.52,closed_loop_learning=.50,generativity=.82,programmability=.72,world_modeling=.70,agency=.72,feedback_gain=.56),
]

BY_CODE = {p.code: p for p in PRIMITIVES}

@dataclass
class Candidate:
    components: Dict[str, float]
    process_tags: List[str] = field(default_factory=list)
    archetype: str = "LAPIS_UNIVERSAL"
    source: str = "generated"
    score: float = 0.0
    hash16: str = ""
    objectives: Dict[str, float] = field(default_factory=dict)
    notes: Dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> "Candidate":
        comps = {k: max(0.0, float(v)) for k, v in self.components.items() if k in BY_CODE and float(v) > 0}
        s = sum(comps.values())
        if s <= 0:
            comps = {"BACTERIAL_CELLULOSE_MATRIX": 1.0}
            s = 1.0
        return Candidate({k: v/s for k, v in comps.items()}, list(self.process_tags), self.archetype, self.source, self.score, self.hash16, dict(self.objectives), dict(self.notes))

    def text(self) -> str:
        c = self.normalized()
        return c.archetype + " " + " ".join(f"{k}:{v:.6f}" for k,v in sorted(c.components.items())) + " " + " ".join(sorted(c.process_tags))

def now_iso(): return datetime.now(timezone.utc).isoformat()
def ensure_dir(p): Path(p).mkdir(parents=True, exist_ok=True)
def sha16(s: str): return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]
def write_json(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
def append_jsonl(path, row):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f: f.write(json.dumps(row, ensure_ascii=False) + "\n")
def write_csv(path, rows, fields):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in rows: w.writerow({k:r.get(k,"") for k in fields})
def read_csv(path):
    path = Path(path)
    if not path.exists(): return []
    with path.open("r", encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))

def torch_info():
    try:
        import torch
        info = {"torch_available": True, "torch_version": getattr(torch, "__version__", "unknown"), "cuda_available": torch.cuda.is_available(), "device": "cuda" if torch.cuda.is_available() else "cpu"}
        if torch.cuda.is_available():
            info["cuda_device_count"] = torch.cuda.device_count()
            info["cuda_device_name"] = torch.cuda.get_device_name(0)
            info["cuda_capability"] = ".".join(map(str, torch.cuda.get_device_capability(0)))
        else:
            info["cuda_device_count"] = 0
        return info
    except Exception as exc:
        return {"torch_available": False, "cuda_available": False, "device": "cpu", "error": str(exc)}

def weighted(c: Candidate, attr: str) -> float:
    c = c.normalized()
    return sum(frac * getattr(BY_CODE[code], attr) for code, frac in c.components.items())

def rolefrac(c: Candidate, role_or_family: str) -> float:
    c = c.normalized()
    return sum(frac for code, frac in c.components.items() if BY_CODE[code].role == role_or_family or BY_CODE[code].family == role_or_family)

def phase_balance(c: Candidate) -> Dict[str, float]:
    return {
        "matrix_like": rolefrac(c,"matrix") + rolefrac(c,"binder") + rolefrac(c,"hydrogel") + rolefrac(c,"crosslinker") + rolefrac(c,"adhesion") + rolefrac(c,"weak_acid") + rolefrac(c,"plasticizer"),
        "mineral_like": rolefrac(c,"mineral") + rolefrac(c,"biomineral") + rolefrac(c,"platelet"),
        "sorbent_like": rolefrac(c,"sorbent") + rolefrac(c,"carbon"),
        "catalyst_like": rolefrac(c,"catalyst") + rolefrac(c,"photocatalyst") + rolefrac(c,"redox_catalyst") + rolefrac(c,"biocatalyst") + rolefrac(c,"catalyst_support") + rolefrac(c,"enzyme"),
        "energy_like": rolefrac(c,"energy") + rolefrac(c,"conductive_polymer") + rolefrac(c,"advanced"),
        "bio_process_like": rolefrac(c,"bio_process"),
        "engine_like": rolefrac(c,"meta_engine"),
        "memory_like": rolefrac(c,"memory"),
        "generator_like": rolefrac(c,"engine") + rolefrac(c,"interpreter"),
        "rule_editor_like": rolefrac(c,"rule_editor"),
        "closed_loop_like": rolefrac(c,"closed_loop") + rolefrac(c,"optimizer"),
        "safety_gate_like": rolefrac(c,"safety_gate"),
        "canvas_like": rolefrac(c,"canvas_layer"),
        "surface_like": rolefrac(c,"surface") + rolefrac(c,"clarity_gate"),
        "containment_like": rolefrac(c,"containment") + rolefrac(c,"stage_protocol"),
        "scene_protocol_like": rolefrac(c,"stage_protocol") + rolefrac(c,"memory_field") + rolefrac(c,"creative_seed"),
    }

def max_single_component(c: Candidate) -> float:
    c = c.normalized()
    return max(c.components.values()) if c.components else 0.0

def hard_reject(c: Candidate) -> Tuple[bool, str]:
    txt = (c.source + " " + c.archetype + " " + " ".join(c.process_tags) + " " + " ".join(c.components.keys())).upper()
    for bad in BANNED_TOKENS:
        if bad in txt:
            return True, f"banned_token:{bad}"

    c = c.normalized()
    ph = phase_balance(c)
    max_single = 0.56 if c.archetype in ("LAPIS_DEMIURGE","LAPIS_WORLD_REWRITER") else 0.62
    if max_single_component(c) > max_single:
        return True, f"single_component_collapse:{max_single_component(c):.3f}"

    n_comp = len([v for v in c.components.values() if v > 0.008])
    min_comp = 5 if c.archetype in ("LAPIS_DEMIURGE","LAPIS_WORLD_REWRITER") else 3
    if n_comp < min_comp:
        return True, "not_enough_components"

    if c.archetype in ("LAPIS_CANVAS","LAPIS_STAGEKEEPER"):
        if ph["canvas_like"] < 0.24:
            return True, "canvas_layer_floor"
        if weighted(c, "surface_readiness") < 0.25:
            return True, "canvas_surface_floor"
        if weighted(c, "signal_clarity") < 0.25:
            return True, "canvas_signal_floor"
        if c.archetype == "LAPIS_STAGEKEEPER" and weighted(c, "safe_containment") < 0.38:
            return True, "stagekeeper_containment_floor"
    elif c.archetype in ("LAPIS_DEMIURGE","LAPIS_WORLD_REWRITER"):
        if ph["engine_like"] < 0.25:
            return True, "demiurge_engine_floor"
        if weighted(c, "rule_rewriting") < (0.32 if c.archetype=="LAPIS_WORLD_REWRITER" else 0.20):
            return True, "demiurge_rule_rewriting_floor"
        if weighted(c, "closed_loop_learning") < (0.22 if c.archetype=="LAPIS_WORLD_REWRITER" else 0.30):
            return True, "demiurge_closed_loop_floor"
        if ph["safety_gate_like"] < 0.03:
            return True, "demiurge_requires_safety_gate"
    else:
        if ph["matrix_like"] < 0.04 and c.archetype not in ("LAPIS_CATALYST","LAPIS_ENERGY"):
            return True, "not_enough_body_matrix"
        if ph["catalyst_like"] > 0.68:
            return True, "too_much_catalyst_phase"
        if rolefrac(c, "advanced") > 0.32:
            return True, "too_much_expert_only_advanced_phase"
        if weighted(c, "low_hazard") < 0.43:
            return True, "hazard_score_too_low"

    return False, ""


def mean_vals(values: List[float]) -> float:
    values = [max(0.0, min(1.0, float(v))) for v in values]
    if not values:
        return 0.0
    return sum(values) / len(values)

def compute_birth_gate(c: Candidate, obj: Dict[str, float], base_score: float) -> Dict[str, Any]:
    """Birth-Gate layer.

    A candidate may be powerful, but power alone does not make it ready.
    It must be visible, contained, testable, and expert-reviewable.
    """
    material_score = max(0.0, min(1.0, float(base_score)))

    canvas_score = mean_vals([
        obj.get("noise_removal", 0),
        obj.get("surface_readiness", 0),
        obj.get("signal_clarity", 0),
        obj.get("scene_preparation", 0),
    ])

    stagekeeper_score = mean_vals([
        obj.get("safe_containment", 0),
        obj.get("scene_preparation", 0),
        obj.get("signal_clarity", 0),
        obj.get("low_hazard", 0),
        obj.get("testability", 0),
    ])

    demiurge_score = mean_vals([
        obj.get("rule_rewriting", 0),
        obj.get("closed_loop_learning", 0),
        obj.get("generativity", 0),
        obj.get("programmability", 0),
        obj.get("world_modeling", 0),
        obj.get("feedback_gain", 0),
    ])

    hypothesis_visibility = mean_vals([
        obj.get("signal_clarity", 0),
        obj.get("surface_readiness", 0),
        obj.get("testability", 0),
        obj.get("noise_removal", 0),
    ])

    containment_integrity = mean_vals([
        obj.get("safe_containment", 0),
        obj.get("low_hazard", 0),
        obj.get("bio_safety", 0),
        obj.get("durability", 0),
        obj.get("testability", 0),
    ])

    scene_viability = mean_vals([
        canvas_score,
        stagekeeper_score,
        hypothesis_visibility,
        containment_integrity,
    ])

    # Expert gate is intentionally conservative but not mystical:
    # it rewards testability, low hazard, and explicit expert validation boundary.
    expert_gate = mean_vals([
        obj.get("testability", 0),
        obj.get("low_hazard", 0),
        containment_integrity,
        1.0 if "EXPERT_VALIDATION_REQUIRED" in c.process_tags else 0.72,
    ])

    birth_readiness = mean_vals([
        scene_viability,
        containment_integrity,
        hypothesis_visibility,
        expert_gate,
        0.55 * demiurge_score + 0.45 * canvas_score,
    ])

    # Multiplicative barrier: a brilliant hypothesis with an unsafe or noisy scene
    # must not jump into champions by raw material score alone.
    final_priority = material_score * max(0.08, scene_viability) * max(0.08, containment_integrity) * max(0.08, hypothesis_visibility) * max(0.08, expert_gate)

    gate_status = "PASSED"
    reasons = []

    if obj.get("creative_potential", 0) > 0.80 and obj.get("safe_containment", 0) < 0.30:
        gate_status = "REJECTED"
        reasons.append("UNSTABLE_BIRTH: creative_potential_high_but_safe_containment_low")

    if containment_integrity < 0.35:
        gate_status = "REJECTED"
        reasons.append("CONTAINMENT_INTEGRITY_LOW")

    if hypothesis_visibility < 0.32:
        gate_status = "REVIEW"
        reasons.append("HYPOTHESIS_VISIBILITY_LOW")

    if scene_viability < 0.32:
        gate_status = "REVIEW" if gate_status != "REJECTED" else gate_status
        reasons.append("SCENE_VIABILITY_LOW")

    if expert_gate < 0.40:
        gate_status = "REJECTED"
        reasons.append("EXPERT_GATE_LOW")

    if c.notes.get("rejected"):
        gate_status = "REJECTED"
        reasons.append("HARD_REJECT:" + str(c.notes.get("reject_reason", "")))

    # Meta archetypes are allowed to have lower material-like scores, but still need gates.
    if c.archetype in ("LAPIS_DEMIURGE", "LAPIS_WORLD_REWRITER"):
        final_priority = mean_vals([material_score, demiurge_score]) * max(0.10, expert_gate) * max(0.10, hypothesis_visibility)
        if demiurge_score < 0.38:
            gate_status = "REVIEW" if gate_status != "REJECTED" else gate_status
            reasons.append("DEMIURGE_SCORE_LOW")

    if c.archetype in ("LAPIS_CANVAS", "LAPIS_STAGEKEEPER"):
        final_priority = mean_vals([material_score, canvas_score, stagekeeper_score]) * max(0.10, expert_gate)
        if canvas_score < 0.38:
            gate_status = "REVIEW" if gate_status != "REJECTED" else gate_status
            reasons.append("CANVAS_SCORE_LOW")

    return {
        "material_score": material_score,
        "canvas_score": canvas_score,
        "stagekeeper_score": stagekeeper_score,
        "demiurge_score": demiurge_score,
        "scene_viability": scene_viability,
        "birth_readiness": birth_readiness,
        "containment_integrity": containment_integrity,
        "hypothesis_visibility": hypothesis_visibility,
        "expert_gate": expert_gate,
        "final_priority": max(0.0, min(1.0, final_priority)),
        "gate_status": gate_status,
        "gate_reason": "; ".join(reasons) if reasons else "OK",
    }


def evaluate(c: Candidate) -> Dict[str, float]:
    c = c.normalized()
    ph = phase_balance(c)

    transformation = weighted(c,"transformation") + 0.18*min(ph["catalyst_like"], ph["matrix_like"]+ph["mineral_like"]+ph["sorbent_like"]) + 0.08*min(ph["bio_process_like"], ph["matrix_like"])
    purification = weighted(c,"purification") + 0.20*min(ph["sorbent_like"]+ph["mineral_like"], ph["matrix_like"]+ph["catalyst_like"]+ph["sorbent_like"])
    self_healing = weighted(c,"self_healing") + 0.20*min(rolefrac(c,"hydrogel")+rolefrac(c,"binder")+rolefrac(c,"adhesion")+rolefrac(c,"plasticizer"), ph["matrix_like"]+ph["bio_process_like"])
    structure_strength = weighted(c,"structure_strength") + 0.20*min(ph["matrix_like"], ph["mineral_like"]+ph["sorbent_like"]) + 0.08*min(rolefrac(c,"crosslinker")+rolefrac(c,"adhesion"), ph["matrix_like"])
    durability = weighted(c,"durability") + 0.16*min(ph["mineral_like"]+ph["sorbent_like"], ph["matrix_like"]+ph["catalyst_like"]) + 0.05*("LOW_HAZARD_GATE" in c.process_tags)
    energy_conversion = weighted(c,"energy_conversion") + 0.18*min(ph["energy_like"]+ph["catalyst_like"], ph["matrix_like"]+ph["mineral_like"]+ph["sorbent_like"])
    biomineralization = weighted(c,"biomineralization") + 0.25*min(rolefrac(c,"biomineral")+ph["bio_process_like"], ph["matrix_like"]+ph["mineral_like"])

    # Demiurge meta features:
    rule_rewriting = weighted(c,"rule_rewriting") + 0.16*min(ph["rule_editor_like"]+ph["generator_like"], ph["memory_like"]+ph["closed_loop_like"])
    autocatalysis = weighted(c,"autocatalysis") + 0.14*min(ph["closed_loop_like"], ph["engine_like"])
    closed_loop_learning = weighted(c,"closed_loop_learning") + 0.18*min(ph["closed_loop_like"]+ph["memory_like"], ph["safety_gate_like"]+ph["engine_like"])
    generativity = weighted(c,"generativity") + 0.18*min(ph["generator_like"]+rolefrac(c,"engine"), ph["world_modeling"] if "world_modeling" in ph else ph["engine_like"])
    programmability = weighted(c,"programmability") + 0.10*min(ph["rule_editor_like"]+ph["engine_like"], ph["memory_like"]+ph["closed_loop_like"])
    world_modeling = weighted(c,"world_modeling") + 0.14*min(rolefrac(c,"world_model")+ph["memory_like"], ph["closed_loop_like"]+ph["engine_like"])
    agency = weighted(c,"agency") + 0.12*min(ph["rule_editor_like"]+ph["closed_loop_like"], ph["safety_gate_like"]+ph["engine_like"])
    feedback_gain = weighted(c,"feedback_gain") + 0.18*min(ph["closed_loop_like"]+ph["safety_gate_like"], ph["memory_like"]+ph["engine_like"])

    noise_removal = weighted(c,"noise_removal") + 0.16*min(ph["sorbent_like"]+ph["surface_like"]+ph["canvas_like"], ph["containment_like"]+ph["matrix_like"]+ph["engine_like"])
    surface_readiness = weighted(c,"surface_readiness") + 0.18*min(ph["surface_like"]+ph["canvas_like"], ph["containment_like"]+ph["scene_protocol_like"]+ph["matrix_like"])
    signal_clarity = weighted(c,"signal_clarity") + 0.16*min(ph["surface_like"]+ph["memory_like"]+ph["canvas_like"], ph["closed_loop_like"]+ph["containment_like"]+ph["testability"] if "testability" in ph else ph["scene_protocol_like"])
    safe_containment = weighted(c,"safe_containment") + 0.18*min(ph["containment_like"]+ph["safety_gate_like"]+ph["canvas_like"], ph["matrix_like"]+ph["engine_like"]+ph["scene_protocol_like"])
    scene_preparation = weighted(c,"scene_preparation") + 0.20*min(ph["canvas_like"]+ph["scene_protocol_like"]+ph["matrix_like"], ph["sorbent_like"]+ph["engine_like"]+ph["containment_like"])
    creative_potential = weighted(c,"creative_potential") + 0.16*min(ph["canvas_like"]+ph["generator_like"]+ph["scene_protocol_like"], ph["signal_clarity"] if "signal_clarity" in ph else ph["surface_like"]+ph["closed_loop_like"])

    vals = [transformation,purification,self_healing,structure_strength,durability,weighted(c,"bio_safety"),energy_conversion,biomineralization]
    clipped = [max(0,min(1,x)) for x in vals]
    unity_bonus = min(clipped)*0.05 + (1.0-statistics.pstdev(clipped))*0.03

    meta_vals = [rule_rewriting, autocatalysis, closed_loop_learning, generativity, programmability, world_modeling, agency, feedback_gain]
    meta_clip = [max(0,min(1,x)) for x in meta_vals]
    demiurge_bonus = min(meta_clip)*0.06 + (1.0-statistics.pstdev(meta_clip))*0.035

    obj = {
        "transformation": transformation + unity_bonus,
        "purification": purification + 0.5*unity_bonus,
        "self_healing": self_healing + 0.5*unity_bonus,
        "structure_strength": structure_strength + 0.4*unity_bonus,
        "durability": durability + 0.4*unity_bonus,
        "bio_safety": weighted(c,"bio_safety"),
        "energy_conversion": energy_conversion + 0.5*unity_bonus,
        "biomineralization": biomineralization + 0.5*unity_bonus,
        "accessibility": weighted(c,"accessibility"),
        "testability": weighted(c,"testability"),
        "low_hazard": weighted(c,"low_hazard"),

        "rule_rewriting": rule_rewriting + demiurge_bonus,
        "autocatalysis": autocatalysis + 0.5*demiurge_bonus,
        "closed_loop_learning": closed_loop_learning + 0.7*demiurge_bonus,
        "generativity": generativity + 0.7*demiurge_bonus,
        "programmability": programmability + 0.5*demiurge_bonus,
        "world_modeling": world_modeling + 0.6*demiurge_bonus,
        "agency": agency + 0.5*demiurge_bonus,
        "feedback_gain": feedback_gain + 0.7*demiurge_bonus,

        "noise_removal": noise_removal,
        "surface_readiness": surface_readiness,
        "signal_clarity": signal_clarity,
        "safe_containment": safe_containment,
        "scene_preparation": scene_preparation,
        "creative_potential": creative_potential,

        "raw_density": weighted(c,"density"),
        "unity_bonus": unity_bonus,
        "demiurge_bonus": demiurge_bonus,
        **ph,
    }
    for k in FEATURES:
        obj[k] = max(0,min(1,obj.get(k,0)))
    return obj

def score_candidate(c: Candidate, archetype: str = None) -> Candidate:
    if archetype:
        c.archetype = archetype
    c = c.normalized()
    obj = evaluate(c)
    rejected, reason = hard_reject(c)
    weights = TARGETS.get(c.archetype, TARGETS["LAPIS_UNIVERSAL"])
    score = sum(weights.get(k,0)*obj.get(k,0) for k in FEATURES)

    if c.archetype == "LAPIS_CANVAS":
        if obj["surface_readiness"] < 0.42: score *= 0.78
        if obj["signal_clarity"] < 0.40: score *= 0.82
        if obj["scene_preparation"] < 0.40: score *= 0.82
    elif c.archetype == "LAPIS_STAGEKEEPER":
        if obj["safe_containment"] < 0.48: score *= 0.76
        if obj["scene_preparation"] < 0.44: score *= 0.82
    elif c.archetype == "LAPIS_DEMIURGE":
        if obj["closed_loop_learning"] < 0.35: score *= 0.78
        if obj["rule_rewriting"] < 0.30: score *= 0.82
        if obj["generativity"] < 0.35: score *= 0.82
    elif c.archetype == "LAPIS_WORLD_REWRITER":
        if obj["rule_rewriting"] < 0.42: score *= 0.76
        if obj["world_modeling"] < 0.35: score *= 0.82
    elif c.archetype == "LAPIS_UNIVERSAL":
        if obj["transformation"] < 0.25: score *= 0.88
        if obj["purification"] < 0.25: score *= 0.88
        if obj["closed_loop_learning"] < 0.20: score *= 0.93

    base_score = max(0, min(1, score))
    if rejected:
        base_score = 0.0

    notes = {
        "archetype": c.archetype,
        "archetype_description": ARCHETYPE_DESCRIPTIONS.get(c.archetype,""),
        "rejected": rejected,
        "reject_reason": reason,
        "boundary": "Research vector only, not a synthesis protocol.",
        "literal_transmutation_claim": False,
        "elixir_claim": False,
        "hazardous_synthesis_protocol": False,
        "certified_material_claim": False,
        "dangerous_chemistry_instructions": False,
        "demiurge_layer": c.archetype in ("LAPIS_DEMIURGE","LAPIS_WORLD_REWRITER"),
        "birth_gate_layer": True,
    }

    tmp = Candidate(c.components, c.process_tags, c.archetype, c.source, base_score, sha16(c.text()), obj, notes)
    gate = compute_birth_gate(tmp, obj, base_score)
    obj.update({k: v for k, v in gate.items() if isinstance(v, (int, float))})
    notes.update({"gate_status": gate["gate_status"], "gate_reason": gate["gate_reason"]})

    # v0.1.5: champions are ranked by final_priority, not raw material score.
    final_score = gate["final_priority"]
    if gate["gate_status"] == "REJECTED":
        final_score *= 0.20
    elif gate["gate_status"] == "REVIEW":
        final_score *= 0.62

    return Candidate(c.components, c.process_tags, c.archetype, c.source, max(0,min(1,final_score)), sha16(c.text()), obj, notes)

def archetype_bias(archetype: str) -> Dict[str,float]:
    b = {p.family:1.0 for p in PRIMITIVES}
    b.update({p.role:1.0 for p in PRIMITIVES})
    if archetype=="LAPIS_CATALYST":
        b.update({"photocatalyst":3.2,"oxide":2.6,"enzyme":2.2,"catalyst":2.4,"biocatalyst":2.2,"carbon":1.4})
    elif archetype=="LAPIS_PURIFIER":
        b.update({"carbon":3.2,"sorbent":3.2,"mineral":2.1,"biopolymer":1.3})
    elif archetype=="LAPIS_HEALER":
        b.update({"biopolymer":3.0,"polymer":2.3,"hydrogel":2.5,"bioactive":2.0,"bioinspired":2.0,"binder":2.0})
    elif archetype=="LAPIS_STONE":
        b.update({"mineral":3.0,"biomineral":2.8,"biopolymer":1.6,"carbon":1.4,"matrix":1.7})
    elif archetype=="LAPIS_LIFE":
        b.update({"biopolymer":2.6,"bio_process":2.8,"enzyme":2.0,"biomineral":1.8,"bioactive":1.6})
    elif archetype=="LAPIS_ENERGY":
        b.update({"conductive_polymer":3.2,"photocatalyst":2.8,"oxide":2.2,"carbon":2.3,"energy":2.8})
    elif archetype=="LAPIS_BIOMINERAL":
        b.update({"biomineral":3.5,"bio_process":3.2,"mineral":2.0,"biopolymer":1.8})
    elif archetype=="LAPIS_LOWHAZARD":
        b.update({"biopolymer":2.5,"mineral":1.8,"biomineral":1.8,"enzyme":1.4,"modifier":1.5})
    elif archetype in ("LAPIS_CANVAS","LAPIS_STAGEKEEPER"):
        b.update({"canvas_layer":4.0,"surface":3.2,"clarity_gate":3.2,"containment":3.4,"stage_protocol":3.4,"memory_field":2.4,"creative_seed":2.5,"sorbent":2.0,"mineral":1.6,"biopolymer":1.4})
        if archetype=="LAPIS_STAGEKEEPER":
            b.update({"containment":4.5,"stage_protocol":4.0,"safety_gate":2.4})
    elif archetype in ("LAPIS_DEMIURGE","LAPIS_WORLD_REWRITER"):
        b.update({"meta_engine":4.0,"engine":3.0,"optimizer":3.0,"closed_loop":3.4,"memory":2.7,"rule_editor":3.5,"world_model":3.0,"safety_gate":2.6,"publication":2.0,"interpreter":2.6})
        if archetype=="LAPIS_WORLD_REWRITER":
            b.update({"rule_editor":4.5,"interpreter":3.4,"world_model":3.6,"engine":3.2})
    return b

def choose(rng: random.Random, items: List[Primitive], bias: Dict[str,float]) -> Primitive:
    weights = [(bias.get(p.family,1)*bias.get(p.role,1)*(0.25+p.low_hazard+p.testability*0.25+sum(getattr(p,k) for k in META_FEATURES)*0.06)) for p in items]
    x = rng.random()*sum(weights)
    acc = 0
    for p,w in zip(items, weights):
        acc += w
        if acc >= x:
            return p
    return items[-1]

def random_candidate(rng: random.Random, archetype: str) -> Candidate:
    bias = archetype_bias(archetype)
    comps = {}

    if archetype in ("LAPIS_CANVAS","LAPIS_STAGEKEEPER"):
        canvas = [p for p in PRIMITIVES if p.family=="canvas_layer"]
        essentials = ["CLEAN_CANVAS_SURFACE","SIGNAL_CLARITY_GATE","SAFE_CONTAINMENT_MATRIX","REPRODUCIBLE_SCENE_PROTOCOL"]
        for code in essentials:
            comps[code] = rng.uniform(0.04,0.20)
        for _ in range(rng.randint(2,5)):
            p = choose(rng, canvas + [BY_CODE[k] for k in ["ZEOLITE_SAFE","ACTIVATED_CARBON_SAFE","BACTERIAL_CELLULOSE_MATRIX","CLAY_PLATELET_BARRIER","CHITOSAN_BINDER"]], bias)
            comps[p.code] = comps.get(p.code,0)+rng.uniform(0.02,0.18)
        tags = ["LOW_HAZARD_GATE","EXPERT_VALIDATION_REQUIRED","CLEAN_CANVAS","LOW_NOISE_FIELD","SAFE_STAGE"]
        if archetype=="LAPIS_STAGEKEEPER":
            tags += ["SAFE_CONTAINMENT","REPRODUCIBLE_SCENE"]
    elif archetype in ("LAPIS_DEMIURGE","LAPIS_WORLD_REWRITER"):
        meta = [p for p in PRIMITIVES if p.family=="meta_engine"]
        # Force essential loop pieces.
        essentials = ["GPT_TRANSFORMER_ENGINE","ACTIVE_LEARNING_AUTOLAB","SCORING_FUNCTION_MUTATOR","KNOWLEDGE_GRAPH_MEMORY","EXPERT_REVIEW_GATE"]
        for code in essentials:
            comps[code] = rng.uniform(0.04,0.20)
        for _ in range(rng.randint(2,5)):
            p = choose(rng, meta, bias)
            comps[p.code] = comps.get(p.code,0)+rng.uniform(0.02,0.18)
        tags = ["LOW_HAZARD_GATE","EXPERT_VALIDATION_REQUIRED","CLOSED_LOOP","RULE_REWRITE","DEMIURGE_LAYER"]
        if archetype=="LAPIS_WORLD_REWRITER":
            tags += ["WORLD_MODEL","SEARCH_SPACE_EDITOR"]
    else:
        body_codes = ["BACTERIAL_CELLULOSE_MATRIX","CHITOSAN_BINDER","ALGINATE_HYDROGEL","PVA_FILM","GELATIN_COLLAGEN_TOKEN"]
        body = [BY_CODE[k] for k in body_codes]
        n_body = 1 if archetype in ("LAPIS_CATALYST","LAPIS_ENERGY") else rng.randint(1,3)
        for _ in range(n_body):
            p = choose(rng, body, bias)
            comps[p.code] = comps.get(p.code,0)+rng.uniform(0.04,0.25)
        for _ in range(rng.randint(3,8)):
            items = [p for p in PRIMITIVES if p.family!="meta_engine"]
            p = choose(rng, items, bias)
            comps[p.code] = comps.get(p.code,0)+rng.uniform(0.01,0.22)
        # Optional small demiurge aid in material archetypes
        if rng.random() < 0.25:
            comps["ACTIVE_LEARNING_AUTOLAB"] = rng.uniform(0.01,0.05)
        tags = ["LOW_HAZARD_GATE","EXPERT_VALIDATION_REQUIRED"]
        tag_probs = {
            "LAMINATED":0.45, "HYDROGEL_NETWORK":0.45 if archetype in ("LAPIS_HEALER","LAPIS_LIFE") else 0.20,
            "BIOMINERALIZED":0.62 if archetype in ("LAPIS_BIOMINERAL","LAPIS_LIFE") else 0.22,
            "PHOTOCATALYTIC_SURFACE":0.62 if archetype in ("LAPIS_CATALYST","LAPIS_ENERGY") else 0.18,
            "ADSORBENT_CORE":0.65 if archetype in ("LAPIS_PURIFIER","LAPIS_UNIVERSAL") else 0.30,
            "SELF_HEALING_LAYER":0.66 if archetype=="LAPIS_HEALER" else 0.24,
            "CONDUCTIVE_TRACE":0.62 if archetype=="LAPIS_ENERGY" else 0.14,
            "STONE_BODY":0.62 if archetype in ("LAPIS_STONE","LAPIS_BIOMINERAL") else 0.25,
            "ANIMA_BIO":0.58 if archetype in ("LAPIS_LIFE","LAPIS_BIOMINERAL") else 0.18,
        }
        for t,p in tag_probs.items():
            if rng.random() < p:
                tags.append(t)

    return score_candidate(Candidate(comps, sorted(set(tags)), archetype, "random"), archetype)

def mutate(c: Candidate, rng: random.Random, rate=0.18) -> Candidate:
    c = c.normalized()
    comps = dict(c.components)
    for code in list(comps):
        if rng.random() < rate:
            comps[code] *= rng.uniform(0.55,1.55)
    if rng.random() < rate:
        p = choose(rng, PRIMITIVES, archetype_bias(c.archetype))
        comps[p.code] = comps.get(p.code,0)+rng.uniform(0.01,0.16)
    if len(comps) > 5 and rng.random() < rate:
        comps.pop(sorted(comps,key=comps.get)[0],None)
    tags = list(c.process_tags)
    if rng.random() < rate:
        tags.append(rng.choice(["LAMINATED","HYDROGEL_NETWORK","BIOMINERALIZED","PHOTOCATALYTIC_SURFACE","ADSORBENT_CORE","SELF_HEALING_LAYER","CONDUCTIVE_TRACE","CLOSED_LOOP","RULE_REWRITE","WORLD_MODEL"]))
    return score_candidate(Candidate(comps, sorted(set(tags)), c.archetype, "mutated"), c.archetype)

def crossover(a: Candidate, b: Candidate, rng: random.Random, archetype: str) -> Candidate:
    aa, bb = a.normalized().components, b.normalized().components
    keys = sorted(set(aa)|set(bb))
    alpha = rng.uniform(0.25,0.75)
    comps = {k:alpha*aa.get(k,0)+(1-alpha)*bb.get(k,0) for k in keys}
    tags = sorted(set(a.process_tags)|set(b.process_tags))
    return score_candidate(Candidate(comps,tags,archetype,"crossover"),archetype)

def formula_percent(c: Candidate) -> str:
    c = c.normalized()
    return "; ".join(f"{k}={round(v*100,2)}%" for k,v in sorted(c.components.items(),key=lambda kv:kv[1],reverse=True))

def coarse_key(c: Candidate) -> Tuple[str,...]:
    c = c.normalized()
    return tuple(sorted(k for k,v in c.components.items() if v > 0.055))

def diversity_signature(c: Candidate) -> Tuple[str,str,str]:
    c = c.normalized()
    ph = phase_balance(c)
    comps = sorted(c.components.items(), key=lambda kv: kv[1], reverse=True)
    top1 = comps[0][0] if comps else "NONE"
    top2 = comps[1][0] if len(comps)>1 else "NONE"
    dominant = max(["matrix_like","mineral_like","sorbent_like","catalyst_like","energy_like","bio_process_like","engine_like","closed_loop_like"], key=lambda k: ph.get(k,0))
    return (dominant, top1, top2)

def fallback_diverse(rng: random.Random, archetype: str, needed: int, sigs: set) -> List[Candidate]:
    out = []
    for _ in range(8000):
        if len(out) >= needed:
            break
        c = random_candidate(rng, archetype)
        if c.score <= 0:
            continue
        sig = diversity_signature(c)
        if sig in sigs:
            continue
        sigs.add(sig)
        out.append(c)
    return out

def candidate_row(c: Candidate, rank=None) -> Dict[str,Any]:
    return {
        "rank": rank,
        "archetype": c.archetype,
        "score": c.score,
        "hash16": c.hash16,
        "formula_percent": formula_percent(c),
        "components": c.normalized().components,
        "process_tags": c.process_tags,
        "source": c.source,
        "objectives": c.objectives,
        "gate": {
            "gate_status": c.notes.get("gate_status", ""),
            "gate_reason": c.notes.get("gate_reason", ""),
            **{k: c.objectives.get(k, 0) for k in GATE_FEATURES},
        },
        "notes": c.notes,
    }

def write_candidate_csv(path: Path, cands: List[Candidate]):
    fields = ["rank","archetype","score","hash16","formula_percent","source","process_tags"] + FEATURES + GATE_FEATURES + [
        "gate_status","gate_reason",
        "raw_density","matrix_like","mineral_like","sorbent_like","catalyst_like","energy_like",
        "bio_process_like","engine_like","closed_loop_like","rule_editor_like","memory_like",
        "components_json","notes_json"
    ]
    rows = []
    for i,c in enumerate(cands,1):
        o = c.objectives
        rows.append({
            "rank": i, "archetype": c.archetype, "score": round(c.score,8),
            "hash16": c.hash16, "formula_percent": formula_percent(c),
            "source": c.source, "process_tags": " ".join(c.process_tags),
            **{k:round(o.get(k,0),6) for k in FEATURES},
            **{k:round(o.get(k,0),6) for k in GATE_FEATURES},
            "gate_status": c.notes.get("gate_status", ""),
            "gate_reason": c.notes.get("gate_reason", ""),
            "raw_density": round(o.get("raw_density",0),6),
            "matrix_like": round(o.get("matrix_like",0),6),
            "mineral_like": round(o.get("mineral_like",0),6),
            "sorbent_like": round(o.get("sorbent_like",0),6),
            "catalyst_like": round(o.get("catalyst_like",0),6),
            "energy_like": round(o.get("energy_like",0),6),
            "bio_process_like": round(o.get("bio_process_like",0),6),
            "engine_like": round(o.get("engine_like",0),6),
            "closed_loop_like": round(o.get("closed_loop_like",0),6),
            "rule_editor_like": round(o.get("rule_editor_like",0),6),
            "memory_like": round(o.get("memory_like",0),6),
            "components_json": json.dumps(c.normalized().components,ensure_ascii=False),
            "notes_json": json.dumps(c.notes,ensure_ascii=False),
        })
    write_csv(path, rows, fields)

def tiny_transformer_propose(outdir: str, archetype: str, seed: int, n_generate=20) -> List[Candidate]:
    info = torch_info()
    if not info.get("torch_available"):
        return []
    try:
        import torch, torch.nn as nn
        rng = random.Random(seed)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        vocab = ["<BOS>","<EOS>"] + [p.code for p in PRIMITIVES] + [
            "LOW_HAZARD_GATE","EXPERT_VALIDATION_REQUIRED","LAMINATED","HYDROGEL_NETWORK",
            "BIOMINERALIZED","PHOTOCATALYTIC_SURFACE","ADSORBENT_CORE","SELF_HEALING_LAYER",
            "CONDUCTIVE_TRACE","STONE_BODY","CLOSED_LOOP","RULE_REWRITE","WORLD_MODEL","DEMIURGE_LAYER"
        ]
        stoi = {s:i for i,s in enumerate(vocab)}
        itos = {i:s for s,i in stoi.items()}
        seq_len = 18

        pool = sorted([random_candidate(rng, archetype) for _ in range(100)], key=lambda x:x.score, reverse=True)[:70]
        data = []
        for c in pool:
            toks = ["<BOS>"] + sorted(c.components.keys())[:10] + sorted(c.process_tags)[:5] + ["<EOS>"]
            ids = [stoi[t] for t in toks if t in stoi]
            ids = ids[:seq_len] + [stoi["<EOS>"]] * max(0, seq_len-len(ids))
            data.append(ids)
        if not data:
            return []
        x = torch.tensor(data, dtype=torch.long, device=device)

        class TinyGPT(nn.Module):
            def __init__(self, n, dim=72, heads=4, layers=2):
                super().__init__()
                self.tok = nn.Embedding(n, dim)
                self.pos = nn.Embedding(seq_len, dim)
                layer = nn.TransformerEncoderLayer(dim, heads, dim_feedforward=144, batch_first=True)
                self.enc = nn.TransformerEncoder(layer, layers)
                self.lm = nn.Linear(dim, n)
            def forward(self, z):
                b,t = z.shape
                h = self.tok(z) + self.pos(torch.arange(t,device=z.device))[None,:,:]
                mask = torch.triu(torch.ones(t,t,device=z.device), diagonal=1).bool()
                return self.lm(self.enc(h,mask=mask))

        model = TinyGPT(len(vocab)).to(device)
        opt = torch.optim.AdamW(model.parameters(), lr=3e-3)
        loss_fn = nn.CrossEntropyLoss()
        steps = 70 if device=="cuda" else 28
        trace = []
        for step in range(1,steps+1):
            logits = model(x[:,:-1])
            loss = loss_fn(logits.reshape(-1,len(vocab)), x[:,1:].reshape(-1))
            opt.zero_grad(); loss.backward(); opt.step()
            if step in (1,steps):
                trace.append({"step":step,"loss":float(loss.detach().cpu())})
        out = []
        model.eval()
        for _ in range(n_generate):
            ids = [stoi["<BOS>"]]
            for __ in range(seq_len-1):
                inp = torch.tensor([ids], dtype=torch.long, device=device)
                probs = torch.softmax(model(inp)[0,-1]/0.92, dim=-1)
                nxt = int(torch.multinomial(probs,1).item())
                ids.append(nxt)
                if itos[nxt] == "<EOS>":
                    break
            toks = [itos[i] for i in ids]
            comps = {}
            tags = ["LOW_HAZARD_GATE","EXPERT_VALIDATION_REQUIRED"]
            for t in toks:
                if t in BY_CODE:
                    comps[t] = comps.get(t,0)+rng.uniform(0.03,0.18)
                elif t not in ("<BOS>","<EOS>"):
                    tags.append(t)
            if comps:
                out.append(score_candidate(Candidate(comps,sorted(set(tags)),archetype,"tiny_transformer_gpt"),archetype))
        append_jsonl(Path(outdir)/"tiny_transformer_archetypes.jsonl",{"archetype":archetype,"torch":info,"generated":len(out),"trace":trace})
        return out
    except Exception as exc:
        append_jsonl(Path(outdir)/"tiny_transformer_archetypes.jsonl",{"archetype":archetype,"error":str(exc)})
        return []

def run_one_archetype(outdir: str, archetype: str, trials: int, seed: int, use_transformer: bool) -> Dict[str,Any]:
    rng = random.Random(seed)
    pop = [random_candidate(rng, archetype) for _ in range(140)]
    if use_transformer:
        pop.extend(tiny_transformer_propose(outdir, archetype, seed+777, 20))
    best = max(pop, key=lambda c:c.score)
    for _ in range(trials):
        r = rng.random()
        if r < 0.55:
            parent = max(rng.sample(pop, k=min(9,len(pop))), key=lambda c:c.score)
            c = mutate(parent,rng)
        elif r < 0.82:
            a,b = rng.sample(pop,2)
            c = crossover(a,b,rng,archetype)
        else:
            c = random_candidate(rng,archetype)
        pop.append(c)
        pop = sorted(pop, key=lambda c:c.score, reverse=True)[:280]
        if c.score > best.score:
            best = c

    top = []
    seen = set()
    sigs = set()
    for c in sorted(pop, key=lambda c:c.score, reverse=True):
        if c.score <= 0:
            continue
        key = (coarse_key(c), diversity_signature(c))
        if key in seen:
            continue
        seen.add(key)
        sigs.add(diversity_signature(c))
        top.append(c)
        if len(top) >= 20:
            break
    if len(top) < 3:
        top.extend(fallback_diverse(rng, archetype, 3-len(top), sigs))

    arch_dir = Path(outdir)/"archetypes"/archetype
    ensure_dir(arch_dir)
    write_candidate_csv(arch_dir/"top.csv", top)
    write_json(arch_dir/"summary.json",{
        "schema":"JanusLapis/ArchetypeSummary/v1",
        "version":VERSION,
        "generated_at":now_iso(),
        "archetype":archetype,
        "description":ARCHETYPE_DESCRIPTIONS.get(archetype,""),
        "trials":trials,
        "seed":seed,
        "best":candidate_row(best,1),
        "top_csv":str(arch_dir/"top.csv"),
    })
    return {"archetype":archetype,"best":best,"top":top}


def write_birth_gate_outputs(outdir: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    outdir = Path(outdir)
    rows = []
    rejected = []
    for r in results:
        for c in r["top"]:
            o = c.objectives
            row = {
                "archetype": c.archetype,
                "hash16": c.hash16,
                "score_final": round(c.score, 8),
                "formula_percent": formula_percent(c),
                "source": c.source,
                "gate_status": c.notes.get("gate_status", ""),
                "gate_reason": c.notes.get("gate_reason", ""),
                "material_score": round(o.get("material_score",0), 6),
                "canvas_score": round(o.get("canvas_score",0), 6),
                "stagekeeper_score": round(o.get("stagekeeper_score",0), 6),
                "demiurge_score": round(o.get("demiurge_score",0), 6),
                "scene_viability": round(o.get("scene_viability",0), 6),
                "birth_readiness": round(o.get("birth_readiness",0), 6),
                "containment_integrity": round(o.get("containment_integrity",0), 6),
                "hypothesis_visibility": round(o.get("hypothesis_visibility",0), 6),
                "expert_gate": round(o.get("expert_gate",0), 6),
                "final_priority": round(o.get("final_priority",0), 6),
                "creative_potential": round(o.get("creative_potential",0), 6),
                "safe_containment": round(o.get("safe_containment",0), 6),
                "signal_clarity": round(o.get("signal_clarity",0), 6),
                "process_tags": " ".join(c.process_tags),
                "components_json": json.dumps(c.normalized().components, ensure_ascii=False),
            }
            rows.append(row)
            if c.notes.get("gate_status") in ("REJECTED", "REVIEW"):
                rejected.append(row)

    fields = list(rows[0].keys()) if rows else []
    write_csv(outdir/"janus_lapis_decision_chain.csv", rows, fields)
    write_csv(outdir/"janus_lapis_birth_gates.csv", sorted(rows, key=lambda x: float(x["final_priority"]), reverse=True), fields)
    write_csv(outdir/"janus_lapis_rejected_by_gate.csv", rejected, fields)

    result = {
        "schema": "JanusLapis/BirthGateOutputs/v1",
        "version": VERSION,
        "generated_at": now_iso(),
        "decision_chain_csv": str(outdir/"janus_lapis_decision_chain.csv"),
        "birth_gates_csv": str(outdir/"janus_lapis_birth_gates.csv"),
        "rejected_by_gate_csv": str(outdir/"janus_lapis_rejected_by_gate.csv"),
        "rows": len(rows),
        "rejected_or_review": len(rejected),
        "boundary": "Computational research vectors and expert-review requests only. No literal transmutation claim, elixir claim, hazardous synthesis protocol, certified material claim, or instructions for dangerous chemistry.",
    }
    write_json(outdir/"janus_lapis_birth_gate_summary.json", result)
    return result


def run_all(outdir: str, trials_per_archetype: int, seed: int, use_transformer: bool) -> Dict[str,Any]:
    ensure_dir(outdir)
    results = []
    for idx,a in enumerate(TARGETS):
        print(f"[Janus-Lapis] {idx+1}/{len(TARGETS)} {a}", flush=True)
        results.append(run_one_archetype(outdir,a,trials_per_archetype,seed+idx*101,use_transformer))
    champions = [r["best"] for r in results]
    union = []
    for r in results:
        union.extend(r["top"][:4])
    write_candidate_csv(Path(outdir)/"janus_lapis_champions.csv",champions)
    write_candidate_csv(Path(outdir)/"janus_lapis_all_archetypes.csv",union)
    birth_gate_outputs = write_birth_gate_outputs(outdir, results)
    summary = {
        "schema":"JanusLapis/AllArchetypes/v1",
        "version":VERSION,
        "generated_at":now_iso(),
        "repo_name":"janus-lapis",
        "engine":"LapisModernGPT",
        "edition":"Birth-Gate Edition",
        "trials_per_archetype":trials_per_archetype,
        "seed":seed,
        "use_transformer":use_transformer,
        "torch":torch_info(),
        "banned_tokens":sorted(BANNED_TOKENS),
        "champions":[candidate_row(c,i+1) for i,c in enumerate(champions)],
        "champions_csv":str(Path(outdir)/"janus_lapis_champions.csv"),
        "all_archetypes_csv":str(Path(outdir)/"janus_lapis_all_archetypes.csv"),
        "decision_chain_csv":str(Path(outdir)/"janus_lapis_decision_chain.csv"),
        "birth_gates_csv":str(Path(outdir)/"janus_lapis_birth_gates.csv"),
        "rejected_by_gate_csv":str(Path(outdir)/"janus_lapis_rejected_by_gate.csv"),
        "birth_gate_outputs":birth_gate_outputs,
        "demiurge_principle":"The stone is not only a material. The stone is the engine that changes the search space.",
        "birth_gate_principle":"A hypothesis must pass the scene before it can enter the world.",
        "canonical_chain":[
            "LAPIS_PURIFIER cleans matter.",
            "LAPIS_CANVAS prepares the clean surface.",
            "LAPIS_STAGEKEEPER protects the scene.",
            "LAPIS_DEMIURGE creates the new game.",
            "BIRTH_GATE decides whether it is ready to be born.",
        ],
        "boundary":"Computational research vectors and expert-review requests only. No literal transmutation claim, elixir claim, hazardous synthesis protocol, certified material claim, or instructions for dangerous chemistry.",
    }
    write_json(Path(outdir)/"janus_lapis_summary.json",summary)
    return summary

def interpretation(archetype: str) -> str:
    return {
        "LAPIS_UNIVERSAL":"balanced map of many Lapis functions",
        "LAPIS_CATALYST":"modern transmutation as catalysis/resource conversion, not magical metal transmutation",
        "LAPIS_PURIFIER":"matter purification through adsorption/separation/detox",
        "LAPIS_HEALER":"repair through self-healing, damage recovery, biocompatible restoration",
        "LAPIS_STONE":"corpus: stable durable structured matter",
        "LAPIS_LIFE":"anima: life-compatible interface and biological fabrication",
        "LAPIS_ENERGY":"spiritus: light/charge/energy conversion",
        "LAPIS_BIOMINERAL":"living stone: biomineralization and biological mineral architecture",
        "LAPIS_LOWHAZARD":"safe path: accessible, non-toxic, testable candidate space",
        "LAPIS_CANVAS":"clean canvas: purified, low-noise surface where a new game can appear",
        "LAPIS_STAGEKEEPER":"stagekeeper: safe, stable, reproducible scene preparation",
        "LAPIS_DEMIURGE":"the Lapis as discovery engine: closed-loop transformer/search/review system",
        "LAPIS_WORLD_REWRITER":"the Lapis as rule editor: system that changes the search space itself",
    }.get(archetype,"modern Lapis research vector")

def build_lab_request(outdir: str, top_per_archetype=3, replicates=1) -> Dict[str,Any]:
    outdir = Path(outdir)
    lab = outdir/"lab_request"
    ensure_dir(lab)
    rows = []
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    for a in TARGETS:
        top_rows = read_csv(outdir/"archetypes"/a/"top.csv")[:top_per_archetype]
        for idx,r in enumerate(top_rows,1):
            for rep in range(1,replicates+1):
                tests = ["EXPERT_IDENTITY_REVIEW","SAFETY_BOUNDARY_REVIEW","FUNCTIONAL_SCREENING_FOR_ARCHETYPE","NO_HAZARDOUS_SYNTHESIS_WITHOUT_QUALIFIED_LAB"]
                if a in ("LAPIS_CATALYST","LAPIS_ENERGY"):
                    tests.append("SAFE_CATALYTIC_OR_PHOTO_ELECTROCHEMICAL_MODEL_SCREENING")
                if a == "LAPIS_PURIFIER":
                    tests.append("ADSORPTION_OR_SEPARATION_SCREENING")
                if a == "LAPIS_HEALER":
                    tests.append("SELF_HEALING_OR_DAMAGE_RECOVERY_SCREENING")
                if a in ("LAPIS_STONE","LAPIS_BIOMINERAL"):
                    tests.append("STRUCTURE_MECHANICAL_OR_BIOMINERAL_REVIEW")
                if a in ("LAPIS_CANVAS","LAPIS_STAGEKEEPER"):
                    tests += ["LOW_NOISE_SCENE_REVIEW","REPRODUCIBILITY_AND_CONTAINMENT_REVIEW","SURFACE_READINESS_REVIEW"]
                if a in ("LAPIS_DEMIURGE","LAPIS_WORLD_REWRITER"):
                    tests += ["CLOSED_LOOP_DISCOVERY_REVIEW","SEARCH_SPACE_REWRITE_REVIEW","REPRODUCIBILITY_AND_HUMAN_GATE_REVIEW"]
                rows.append({
                    "request_id":f"JL-{date}-{a}-{idx:02d}-R{rep}",
                    "repo":"janus-lapis",
                    "engine":"LapisModernGPT",
                    "version":VERSION,
                    "archetype":a,
                    "archetype_description":ARCHETYPE_DESCRIPTIONS.get(a,""),
                    "rank_within_archetype":idx,
                    "score":r.get("score",""),
                    "hash16":r.get("hash16",""),
                    "formula_percent_research_vector":r.get("formula_percent",""),
                    "process_tags":r.get("process_tags",""),
                    "why_lapis_like":interpretation(a),
                    "requested_tests":" | ".join(tests),
                    "data_status":"REQUEST_FOR_EXPERT_REVIEW_NOT_MEASURED_RESULTS",
                    "claim_boundary":"No literal transmutation claim. No elixir claim. No hazardous synthesis protocol. No certified material claim. No instructions for dangerous chemistry. Computational research vector and expert-review request only.",
                    "components_json":r.get("components_json",""),
                    "objectives_json":json.dumps({k:r.get(k,"") for k in FEATURES + GATE_FEATURES},ensure_ascii=False),
                })
    fields = list(rows[0].keys()) if rows else []
    write_csv(lab/"janus_lapis_external_research_request.csv",rows,fields)
    brief = f"""# JANUS-LAPIS External Research Brief

Generated: {now_iso()}
Version: {VERSION}

JANUS-LAPIS is a respectful modern search for the real functions behind the historical philosopher's stone.

v0.1.3 adds the Demiurge layer.
v0.1.4 adds the Canvas / Stagekeeper layer.

The stone is not only a material.
The stone is also the gate that decides whether a hypothesis is ready to be born.

Material archetypes:
Catalyst, Purifier, Healer, Stone, Life, Energy, Biomineral, LowHazard.

Scene-preparation archetypes:
Canvas, Stagekeeper.

Meta archetypes:
Demiurge, World-Rewriter.

Boundary:
No literal transmutation claim. No elixir claim. No hazardous synthesis protocol.
No certified material claim. No instructions for dangerous chemistry.
All outputs are computational research vectors and expert-review requests.
"""
    (lab/"JANUS_LAPIS_EXTERNAL_RESEARCH_BRIEF.md").write_text(brief,encoding="utf-8")
    result = {
        "schema":"JanusLapis/LabRequest/v1",
        "version":VERSION,
        "generated_at":now_iso(),
        "rows":len(rows),
        "request_csv":str(lab/"janus_lapis_external_research_request.csv"),
        "brief":str(lab/"JANUS_LAPIS_EXTERNAL_RESEARCH_BRIEF.md"),
    }
    write_json(lab/"janus_lapis_lab_request_summary.json",result)
    return result

def build_send_to_reviewers(outdir: str) -> Dict[str,Any]:
    root = Path(outdir)
    send = root/"SEND_TO_REVIEWERS_JANUS_LAPIS"
    if send.exists():
        shutil.rmtree(send)
    ensure_dir(send)
    for name in ["janus_lapis_summary.json","janus_lapis_champions.csv","janus_lapis_all_archetypes.csv","janus_lapis_decision_chain.csv","janus_lapis_birth_gates.csv","janus_lapis_rejected_by_gate.csv","janus_lapis_birth_gate_summary.json","tiny_transformer_archetypes.jsonl"]:
        p = root/name
        if p.exists():
            shutil.copy2(p,send/name)
    arch_send = send/"archetypes"
    ensure_dir(arch_send)
    for a in TARGETS:
        src = root/"archetypes"/a
        if src.exists():
            dst = arch_send/a
            ensure_dir(dst)
            for p in src.glob("*"):
                if p.is_file():
                    shutil.copy2(p,dst/p.name)
    lab_send = send/"lab_request"
    ensure_dir(lab_send)
    for name in ["janus_lapis_external_research_request.csv","JANUS_LAPIS_EXTERNAL_RESEARCH_BRIEF.md","janus_lapis_lab_request_summary.json"]:
        p = root/"lab_request"/name
        if p.exists():
            shutil.copy2(p,lab_send/name)
    (send/"COVER_NOTE.md").write_text("""# JANUS-LAPIS v0.1.5

A modern GPT-guided search space for the real functions behind the philosopher's stone.

Birth-Gate Edition:
The stone is not only a material.
The stone is the clean scene that lets a new game appear.
The stone is also the gate that decides whether a hypothesis is ready to be born.
The stone is also the engine that changes the search space.

Boundary:
No literal transmutation claim, no elixir claim, no hazardous synthesis protocol.
No certified material claim and no instructions for dangerous chemistry.
All outputs are computational research vectors and expert-review requests.
""",encoding="utf-8")
    (send/"README_SEND_THIS.md").write_text("""# SEND_TO_REVIEWERS_JANUS_LAPIS

This package is for expert scientific review.
It maps possible modern Lapis archetypes, scene preparation, Birth-Gate judgment,
and the Demiurge discovery-engine layer.
""",encoding="utf-8")
    zip_path = root/"SEND_TO_REVIEWERS_JANUS_LAPIS.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as z:
        for p in send.rglob("*"):
            z.write(p,Path("SEND_TO_REVIEWERS_JANUS_LAPIS")/p.relative_to(send))
    result = {"schema":"JanusLapis/SendToReviewers/v1","version":VERSION,"generated_at":now_iso(),"zip":str(zip_path),"status":"READY"}
    write_json(root/"send_to_reviewers_janus_lapis_summary.json",result)
    return result

def full_run(outdir: str, trials_per_archetype: int, seed: int, top_per_archetype: int, replicates: int, use_transformer: bool) -> Dict[str,Any]:
    run_all(outdir,trials_per_archetype,seed,use_transformer)
    build_lab_request(outdir,top_per_archetype,replicates)
    return build_send_to_reviewers(outdir)

def build_parser():
    p = argparse.ArgumentParser(description="JANUS-LAPIS / LapisModernGPT v0.1.5")
    p.add_argument("--outdir", default=DEFAULT_OUTDIR)
    sub = p.add_subparsers(dest="cmd", required=True)
    fr = sub.add_parser("full-run")
    fr.add_argument("--trials-per-archetype", type=int, default=3000)
    fr.add_argument("--seed", type=int, default=1618)
    fr.add_argument("--top-per-archetype", type=int, default=3)
    fr.add_argument("--replicates", type=int, default=1)
    fr.add_argument("--no-transformer", action="store_true")
    sub.add_parser("build-send-to-reviewers")
    return p

def main():
    args = build_parser().parse_args()
    if args.cmd == "full-run":
        print(json.dumps(full_run(args.outdir,args.trials_per_archetype,args.seed,args.top_per_archetype,args.replicates,not args.no_transformer),ensure_ascii=False,indent=2))
    elif args.cmd == "build-send-to-reviewers":
        print(json.dumps(build_send_to_reviewers(args.outdir),ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()

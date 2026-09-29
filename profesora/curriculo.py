"""Plan de estudios desde nivel 0 (A0 -> A2), pensado para hispanohablantes.

Cada unidad tiene un objetivo comunicativo, el vocabulario base y el sonido
del inglés que más le cuesta a un hispanohablante en ese punto.
"""

UNIDADES = [
    {
        "titulo": "Saludar y despedirse",
        "objetivo": "Saludar, preguntar cómo está alguien y despedirse.",
        "vocabulario": ["hello", "hi", "good morning", "good afternoon", "good night",
                        "goodbye", "bye", "how are you?", "I'm fine", "thank you", "please"],
        "pronunciacion": "La H inglesa es suave, como un suspiro (hello = 'jélou' con J muy suave), "
                         "no como la J fuerte del español.",
    },
    {
        "titulo": "Presentarse",
        "objetivo": "Decir su nombre, de dónde es y preguntar lo mismo.",
        "vocabulario": ["my name is", "what's your name?", "I'm from Colombia", "where are you from?",
                        "nice to meet you", "yes", "no"],
        "pronunciacion": "Las vocales largas: 'meet' (i larga) vs 'mit'. Estirar la i.",
    },
    {
        "titulo": "Números del 1 al 20",
        "objetivo": "Contar, decir su edad y su número de teléfono.",
        "vocabulario": ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                        "eleven", "twelve", "thirteen", "fifteen", "twenty", "how old are you?"],
        "pronunciacion": "El sonido TH de 'three' y 'thirteen': la punta de la lengua entre los dientes, "
                         "soplando suave (no es 'tri' ni 'fri').",
    },
    {
        "titulo": "El verbo TO BE (ser / estar)",
        "objetivo": "Decir cómo es y cómo está: I am, you are, he is, she is.",
        "vocabulario": ["I am", "you are", "he is", "she is", "we are", "they are",
                        "happy", "tired", "hungry", "busy", "a mother", "a teacher"],
        "pronunciacion": "Contracciones: I'm, you're, she's. En inglés se 'pegan' las palabras.",
    },
    {
        "titulo": "La familia",
        "objetivo": "Hablar de su familia: hijos, esposo, padres, hermanos.",
        "vocabulario": ["mother", "father", "son", "daughter", "husband", "brother", "sister",
                        "family", "I have", "children"],
        "pronunciacion": "La TH suave de 'mother', 'father', 'brother' (como una D con la lengua entre los dientes).",
    },
    {
        "titulo": "Colores y cosas de la casa",
        "objetivo": "Nombrar objetos de la casa y describirlos con colores.",
        "vocabulario": ["red", "blue", "green", "yellow", "black", "white", "house", "kitchen",
                        "table", "chair", "door", "window", "bed", "this is", "it is"],
        "pronunciacion": "No agregar 'e' al inicio: 'es-tudent' no, 'student' sí. "
                         "Y las consonantes finales se pronuncian: 'bed', 'red'.",
    },
    {
        "titulo": "Días, meses y la hora",
        "objetivo": "Decir qué día es, su cumpleaños y qué hora es.",
        "vocabulario": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
                        "today", "tomorrow", "what time is it?", "it's three o'clock", "birthday"],
        "pronunciacion": "'Wednesday' se dice 'uénsdei' (la d no suena). 'Tuesday' vs 'Thursday'.",
    },
    {
        "titulo": "Comida y bebidas",
        "objetivo": "Decir qué le gusta comer y pedir en un restaurante.",
        "vocabulario": ["water", "coffee", "bread", "rice", "chicken", "fruit", "I like", "I don't like",
                        "I would like", "can I have...?", "the check, please"],
        "pronunciacion": "La V de 'very'/'vegetables' con los dientes sobre el labio (distinta a la B).",
    },
    {
        "titulo": "La rutina diaria (presente simple)",
        "objetivo": "Contar lo que hace en un día normal.",
        "vocabulario": ["I wake up", "I work", "I cook", "I eat", "I go to", "I sleep",
                        "every day", "in the morning", "at night", "she works"],
        "pronunciacion": "La S final de 'works', 'eats', 'sleeps': que se escuche.",
    },
    {
        "titulo": "Hacer preguntas",
        "objetivo": "Preguntar qué, dónde, cuándo, quién y cómo.",
        "vocabulario": ["what", "where", "when", "who", "how", "how much", "do you...?", "can you help me?"],
        "pronunciacion": "Entonación: en preguntas de sí/no la voz sube al final.",
    },
    {
        "titulo": "De compras",
        "objetivo": "Preguntar precios, tallas y pagar.",
        "vocabulario": ["how much is it?", "it's expensive", "it's cheap", "I want", "this one",
                        "size", "cash", "card", "dollars"],
        "pronunciacion": "Diferenciar 'ship' / 'sheep' y 'live' / 'leave' (i corta vs i larga).",
    },
    {
        "titulo": "Direcciones y lugares",
        "objetivo": "Preguntar y entender cómo llegar a un lugar.",
        "vocabulario": ["where is...?", "left", "right", "straight", "near", "far", "bank", "hospital",
                        "supermarket", "bathroom", "street"],
        "pronunciacion": "La R inglesa: la lengua no toca el paladar ('right', 'street').",
    },
    {
        "titulo": "El pasado (lo que hice ayer)",
        "objetivo": "Contar lo que hizo ayer con verbos comunes.",
        "vocabulario": ["yesterday", "I was", "I went", "I ate", "I worked", "I cooked", "I watched",
                        "last week"],
        "pronunciacion": "Terminación -ED: 'worked' suena 'uorkt', 'watched' suena 'uacht', no 'uork-ed'.",
    },
    {
        "titulo": "Planes y futuro",
        "objetivo": "Hablar de planes: lo que va a hacer.",
        "vocabulario": ["I'm going to", "tomorrow", "next week", "I will", "I want to", "maybe"],
        "pronunciacion": "'going to' en conversación suena 'gona'. Ritmo natural del inglés.",
    },
    {
        "titulo": "Conversación libre",
        "objetivo": "Mantener conversaciones cortas de la vida diaria mezclando todo lo aprendido.",
        "vocabulario": [],
        "pronunciacion": "Repaso de los sonidos que más le hayan costado.",
    },
]


def unidad(indice: int) -> dict:
    return UNIDADES[max(0, min(indice, len(UNIDADES) - 1))]


def texto_unidad(indice: int) -> str:
    u = unidad(indice)
    vocab = ", ".join(u["vocabulario"]) or "(libre)"
    return (
        f"Unidad {indice + 1} de {len(UNIDADES)}: {u['titulo']}\n"
        f"- Objetivo: {u['objetivo']}\n"
        f"- Vocabulario base: {vocab}\n"
        f"- Foco de pronunciación: {u['pronunciacion']}"
    )

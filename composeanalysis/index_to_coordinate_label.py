def index_to_coordinate_label(index: int, size: int) -> str:
    if index == size * size:
        result = 'pass'
    else:
        # THESE LINES ARE COMMENTED OUT TO REMIND ME TO CHECK MY MATH BEFORE GETTING SO MUCH FARTHER IN THE PROJECT  }:|
        # column_index = index // size
        column_index = index % size
        column = 'ABCDEFGHJKLMNOPQRST'[column_index]

        # row_index = index % size
        row_index = index // size
        row = size - row_index

        result = f'{column}{row}'

    return result

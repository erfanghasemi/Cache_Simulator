import math
from collections import deque

block_size = None
unified_separated = None
associativity = None
write_policy = None
write_miss_policy = None
unified_size = None
instruction_cache_size = None
data_cache_size = None
word_per_block = 0
requests = []


instructions_access_count = 0
instructions_misses_count = 0
instructions_miss_rate = 0
instructions_hit_rate = 0
instructions_replace = 0


data_access_count = 0
data_misses_count = 0
data_miss_rate = 0
data_hit_rate = 0
data_replace = 0

copies_back_words = 0
demand_fetch_blocks = 0


class Cache:

    def __init__(self, block_size, associativity, write_policy, write_miss_policy):
        self.block_size = block_size
        self.associativity = associativity
        self.write_policy = write_policy
        self.write_miss_policy = write_miss_policy


class UnifiedCache(Cache):

    def __init__(self, block_size, associativity, write_policy, write_miss_policy, unified_size):
        super().__init__(block_size, associativity, write_policy, write_miss_policy)
        self.unified_size = unified_size
        self.block_count = int(unified_size / block_size)
        self.set_count = int(self.block_count / self.associativity)
        self.set_blocks_list = []
        self.address_byte_bits = int(math.log(block_size, 2))
        self.address_index_bits = int(math.log(self.block_count, 2))
        self.address_tag_bits = 32 - int((self.address_byte_bits+self.address_index_bits))

    def organize_sets(self):
        for i in range(self.set_count):
            new_set_blocks = SetBlocks(size=self.associativity)
            self.set_blocks_list.append(new_set_blocks)

    def read_request(self, operation, byte_address):
        read_miss_flag = 1
        byte_address = bin(byte_address)[2:].zfill(32)
        block_address = byte_address[:-self.address_byte_bits]
        target_set_index = int(block_address, 10) % self.set_count
        target_block = None
        for block in self.set_blocks_list[target_set_index].list_blocks:

            if block.block_index == block_address[-self.address_index_bits:] and block.block_tag == block_address[:self.address_tag_bits]:
                read_miss_flag = 0
                target_block = block

        if read_miss_flag == 0:
            self.set_blocks_list[target_set_index].resort_set(target_block)

        if read_miss_flag == 1:
            global data_misses_count, instructions_misses_count
            if operation == 0:
                data_misses_count = data_misses_count+1
            elif operation == 2:
                instructions_misses_count = instructions_misses_count+1

            added_block = Block(valid_bit=1, block_index=block_address[-self.address_index_bits:], block_tag=block_address[:self.address_tag_bits])
            global demand_fetch_blocks
            demand_fetch_blocks = demand_fetch_blocks + 1
            self.set_blocks_list[target_set_index].add_block(operation, added_block)

    def write_request(self, byte_address):
        global copies_back_words, data_misses_count, demand_fetch_blocks
        write_miss_flag = 1
        byte_address = bin(byte_address)[2:].zfill(32)
        block_address = byte_address[:-self.address_byte_bits]
        target_set_index = int(block_address, 10) % self.set_count
        target_block = None
        for block in self.set_blocks_list[target_set_index].list_blocks:
            if block.block_index == block_address[-self.address_index_bits:] and block.block_tag == block_address[:self.address_tag_bits]:
                write_miss_flag = 0
                target_block = block
                if write_policy == 'wb':
                    target_block.dirty_bit = 1

                elif write_policy == 'wt':
                    copies_back_words = copies_back_words + 1

        if write_miss_flag == 0:
            self.set_blocks_list[target_set_index].resort_set(target_block)

        if write_miss_flag == 1:
            if write_miss_policy == 'wa':

                added_block = Block(valid_bit=1, block_index=block_address[-self.address_index_bits:],
                                    block_tag=block_address[:self.address_tag_bits])

                demand_fetch_blocks = demand_fetch_blocks + 1
                data_misses_count = data_misses_count+1

                if write_policy == 'wb':
                    added_block.dirty_bit = 1
                elif write_policy == 'wt':
                    copies_back_words = copies_back_words + 1

                self.set_blocks_list[target_set_index].add_block(1, added_block)

            elif write_miss_policy == 'nw':
                copies_back_words = copies_back_words + 1
                data_misses_count = data_misses_count + 1

    def clear_cache(self):
        for set in self.set_blocks_list:
            for block in set.list_blocks:
                if block.dirty_bit == 1:
                    global copies_back_words
                    copies_back_words = copies_back_words + word_per_block


class SeparatedCache(Cache):

    def __init__(self, block_size, associativity, write_policy, write_miss_policy, instruction_cache_size, data_cache_size):
        super().__init__(block_size, associativity, write_policy, write_miss_policy)
        self.instruction_cache_size = instruction_cache_size
        self.data_cache_size = data_cache_size
        self.instruction_block_count = instruction_cache_size / block_size
        self.data_block_count = data_cache_size / block_size
        self.set_instruction_count = int(self.instruction_block_count / self.associativity)
        self.set_data_count = int(self.data_block_count / self.associativity)
        self.set_instructions_blocks_list = []
        self.set_data_blocks_list = []
        self.address_byte_bits = int(math.log(block_size, 2))
        self.d_address_index_bits = int(math.log(self.data_block_count, 2))
        self.i_address_index_bits = int(math.log(self.instruction_block_count, 2))
        self.d_address_tag_bits = 32 - int((self.address_byte_bits + self.d_address_index_bits))
        self.i_address_tag_bits = 32 - int((self.address_byte_bits + self.i_address_index_bits))

    def organize_blocks(self):

        for i in range(self.set_data_count):
            new_set_blocks = SetBlocks(self.associativity)
            self.set_data_blocks_list.append(new_set_blocks)

        for i in range(self.set_instruction_count):
            new_set_blocks = SetBlocks(self.associativity)
            self.set_instructions_blocks_list.append(new_set_blocks)

    def read_request(self, operation, byte_address):
        global data_misses_count, demand_fetch_blocks, instructions_misses_count
        byte_address = bin(byte_address)[2:].zfill(32)
        block_address = byte_address[:-self.address_byte_bits]

        if operation == 0:
            read_data_miss_flag = 1
            data_target_set_index = int(block_address, 10) % self.set_data_count
            target_block = None
            for block in self.set_data_blocks_list[data_target_set_index].list_blocks:

                if block.block_index == block_address[-self.d_address_index_bits:] and block.block_tag == block_address[:self.d_address_tag_bits]:
                    read_data_miss_flag = 0
                    target_block = block

            if read_data_miss_flag == 0:
                self.set_data_blocks_list[data_target_set_index].resort_set(target_block)

            if read_data_miss_flag == 1:
                data_misses_count = data_misses_count + 1
                added_block = Block(valid_bit=1, block_index=block_address[-self.d_address_index_bits:],
                                    block_tag=block_address[:self.d_address_tag_bits])
                demand_fetch_blocks = demand_fetch_blocks + 1
                self.set_data_blocks_list[data_target_set_index].add_block(0, added_block)

        elif operation == 2:
            read_instruction_miss_flag = 1
            instruction_target_set_index = int(block_address, 10) % self.set_instruction_count

            target_block = None
            for block in self.set_instructions_blocks_list[instruction_target_set_index].list_blocks:
                if block.block_index == block_address[-self.i_address_index_bits:] and block.block_tag == block_address[:self.i_address_tag_bits]:
                    read_instruction_miss_flag = 0
                    target_block = block

            if read_instruction_miss_flag == 0:
                self.set_instructions_blocks_list[instruction_target_set_index].resort_set(target_block)

            if read_instruction_miss_flag == 1:
                instructions_misses_count = instructions_misses_count + 1
                added_block = Block(valid_bit=1, block_index=block_address[-self.i_address_index_bits:],
                                    block_tag=block_address[:self.i_address_tag_bits])
                demand_fetch_blocks = demand_fetch_blocks + 1
                self.set_instructions_blocks_list[instruction_target_set_index].add_block(2, added_block)

    def write_request(self, byte_address):
        global copies_back_words, demand_fetch_blocks, data_misses_count
        write_miss_flag = 1
        byte_address = bin(byte_address)[2:].zfill(32)
        block_address = byte_address[:-self.address_byte_bits]
        target_set_index = int(block_address, 10) % self.set_data_count

        target_block = None
        for block in self.set_data_blocks_list[target_set_index].list_blocks:
            if block.block_index == block_address[-self.d_address_index_bits:] and block.block_tag == block_address[:self.d_address_tag_bits]:
                write_miss_flag = 0
                target_block = block
                if write_policy == 'wb':
                    target_block.dirty_bit = 1

                elif write_policy == 'wt':
                    copies_back_words = copies_back_words + 1

        if write_miss_flag == 0:
            self.set_data_blocks_list[target_set_index].resort_set(target_block)

        if write_miss_flag == 1:
            if write_miss_policy == 'wa':

                added_block = Block(valid_bit=1, block_index=block_address[-self.d_address_index_bits:],
                                    block_tag=block_address[:self.d_address_tag_bits])
                demand_fetch_blocks = demand_fetch_blocks + 1
                data_misses_count = data_misses_count + 1

                if write_policy == 'wb':
                    added_block.dirty_bit = 1
                elif write_policy == 'wt':
                    copies_back_words = copies_back_words+1

                self.set_data_blocks_list[target_set_index].add_block(1, added_block)

            elif write_miss_policy == 'nw':
                copies_back_words = copies_back_words + 1
                data_misses_count = data_misses_count + 1

    def clear_cache(self):
        global copies_back_words, word_per_block
        for set in self.set_data_blocks_list:
            for block in set.list_blocks:
                if block.dirty_bit == 1:
                    copies_back_words = copies_back_words + word_per_block

        for set in self.set_instructions_blocks_list:
            for block in set.list_blocks:
                if block.dirty_bit == 1:
                    copies_back_words = copies_back_words + word_per_block


class Block:

    def __init__(self, dirty_bit=0, valid_bit=0, block_tag=None, block_index=None):
        self.dirty_bit = dirty_bit
        self.valid_bit = valid_bit
        self.block_tag = block_tag
        self.block_index = block_index


class SetBlocks:

    def __init__(self, size):
        self.list_blocks = deque()
        self.size = size

    def add_block(self, operation, new_block):

        set_full = 1
        for block in self.list_blocks:
            if block.valid_bit == 0:
                set_full = 0

        if len(self.list_blocks) == self.size:
            global data_replace, instructions_replace
            if operation == 2 and set_full == 1:
                instructions_replace = instructions_replace + 1
            elif operation == 0 and set_full == 1:
                data_replace = data_replace + 1
            elif operation == 1 and set_full == 1:
                data_replace = data_replace + 1

            lost_block = self.list_blocks.pop()
            if lost_block.dirty_bit == 1:
                global copies_back_words
                copies_back_words = copies_back_words + word_per_block
            self.list_blocks.appendleft(new_block)
        else:
            self.list_blocks.appendleft(new_block)

    def resort_set(self, used_block):
        self.list_blocks.remove(used_block)
        self.list_blocks.appendleft(used_block)


def get_information():
    information = input()
    conf_cache = information.split(' - ')

    global block_size, unified_separated, associativity, write_policy, write_miss_policy, word_per_block
    block_size = int(conf_cache[0])
    unified_separated = int(conf_cache[1])
    associativity = int(conf_cache[2])
    write_policy = conf_cache[3]
    write_miss_policy = conf_cache[4]
    word_per_block = int(block_size / 4)

    global unified_size, instruction_cache_size, data_cache_size
    if unified_separated == 0:
        unified_setting = input()
        unified_size = int(unified_setting)
    else:
        separate_setting = input()
        caches_size = separate_setting.split(' - ')
        instruction_cache_size = int(caches_size[0])
        data_cache_size = int(caches_size[1])

    global requests

    while True:

        request = input()
        if request == '':
            return
        request_list = request.split(' ')
        request_list[0] = int(request_list[0])
        request_list[1] = int(request_list[1], 16)
        requests.append(tuple([request_list[0], request_list[1]]))


def show_result():
    global data_miss_rate, data_hit_rate, instructions_miss_rate, instructions_hit_rate, word_per_block
    if data_access_count != 0:
        data_miss_rate = format(round((data_misses_count / data_access_count), 4), '0.4f')
        data_hit_rate = format(round((data_access_count-data_misses_count) / data_access_count, 4), '0.4f')
    else:
        data_miss_rate = '0.0000'
        data_hit_rate = '0.0000'

    if instructions_access_count != 0:
        instructions_miss_rate = format(round((instructions_misses_count / instructions_access_count), 4), '0.4f')
        instructions_hit_rate = format(round((instructions_access_count-instructions_misses_count) / instructions_access_count, 4), '0.4f')
    else:
        instructions_miss_rate = '0.0000'
        instructions_hit_rate = '0.0000'


    print("***CACHE SETTINGS***")
    if unified_separated == 0:
        print("Unified I- D-cache")
        print(f"Size: {unified_size}")
    else:
        print("Split I- D-cache")
        print(f"I-cache size: {instruction_cache_size}")
        print(f"D-cache size: {data_cache_size}")

    print(f"Associativity: {associativity}")
    print(f"Block size: {block_size}")
    if write_policy == 'wb':
        print("Write policy: WRITE BACK")
    elif write_policy == 'wt':
        print("Write policy: WRITE THROUGH")

    if write_miss_policy == 'wa':
        print("Allocation policy: WRITE ALLOCATE")
    elif write_miss_policy == 'nw':
        print("Allocation policy: WRITE NO ALLOCATE")
    print('\n')

    print('***CACHE STATISTICS***')
    print('INSTRUCTIONS')
    print(f'accesses: {instructions_access_count}')
    print(f'misses: {instructions_misses_count}')
    print(f'miss rate: {instructions_miss_rate} (hit rate {instructions_hit_rate})')
    print(f'replace: {instructions_replace}')

    print('DATA')
    print(f'accesses: {data_access_count}')
    print(f'misses: {data_misses_count}')
    print(f'miss rate: {data_miss_rate} (hit rate {data_hit_rate})')
    print(f'replace: {data_replace}')

    print('TRAFFIC (in words)')
    print(f'demand fetch: {int(demand_fetch_blocks * word_per_block)}')
    print(f'copies back: {copies_back_words}')


if __name__ == '__main__':
    get_information()
    if unified_separated == 0:
        unified_cache = UnifiedCache(block_size, associativity, write_policy, write_miss_policy, unified_size)
        unified_cache.organize_sets()
        for operation, address in requests:
            if operation == 0:
                data_access_count = data_access_count+1
                unified_cache.read_request(0, address)

            elif operation == 1:
                data_access_count = data_access_count + 1
                unified_cache.write_request(address)

            elif operation == 2:
                instructions_access_count = instructions_access_count + 1
                unified_cache.read_request(2, address)

        unified_cache.clear_cache()

    elif unified_separated == 1:
        separate_cache = SeparatedCache(block_size, associativity, write_policy, write_miss_policy,instruction_cache_size, data_cache_size)
        separate_cache.organize_blocks()

        for operation, address in requests:
            if operation == 0:
                data_access_count = data_access_count + 1
                separate_cache.read_request(0, address)

            elif operation == 1:
                data_access_count = data_access_count + 1
                separate_cache.write_request(address)

            elif operation == 2:
                instructions_access_count = instructions_access_count + 1
                separate_cache.read_request(2, address)
        separate_cache.clear_cache()

    show_result()

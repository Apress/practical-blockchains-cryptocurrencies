import asyncio
import threading
import time
import secrets

async def fibonacci():
    ctr  = 2
    fib1 = 1
    fib2 = 2
    print("fibonacci number 0"  + "  = "  + "0")
    print("fibonacci number 1"  + "  = " + "1")

    while True:
        tmp  = fib1 + fib2
        fib1 = fib2
        fib2 = tmp 
        message = await print_number(fib2, "F")
        ctr += 1
        time.sleep(1)


async def prime():
    number = 3
    half   = 3 

    while True:
        for ctr in range(half):
            divided = False

            if ctr < 2: continue
            if number%ctr == 0: 
                divided = True
                break

        if divided == False:
            message = await print_number(number, "P")
 
        number += 1
        half = int(number/2) + 1
        time.sleep(1)


async def print_number(number: "int", number_type: "F or P" ):
    #F: fibonacci number, P: Prime Number
    nap = secrets.randbelow(3)
    await asyncio.sleep(nap)

    if number_type == "F":
        print("fibonacci no:    " + " = " + str(number))
    else:    		
        print("prime number no: " + " = " + str(number))
    return "task executed"

async def main():
    await asyncio.gather(fibonacci(), prime())
 
if __name__ == "__main__":
    print("starting program in main thread")
    asyncio.run(main())
    print("ending program") 

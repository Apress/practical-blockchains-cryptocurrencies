import threading
import time
from threading import Lock

balance = 0

def fibonacci():
    ctr  = 2
    fib1 = 1
    fib2 = 2
    print("fibonacci number 0"  + "  = "  + "0")
    print("fibonacci number 1"  + "  = " + "1")

    while True:
        tmp  = fib1 + fib2
        fib1 = fib2
        fib2 = tmp 
        print("fibonacci number " + str(ctr) + "  = " + str(fib2))
        ctr += 1
        time.sleep(1)

def prime():
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
            print("next prime number: " + str(number))
            
        number += 1
        half = int(number/2) + 1
        time.sleep(1)


if __name__ == "__main__":
    print("starting program in main thread")

    #Create the Threads
    t1 = threading.Thread(target=fibonacci, args=(), daemon=True)
    t2 = threading.Thread(target=prime, args=(), daemon=True)
   
    # start the threads
    t1.start()
    t2.start()
    mutex = Lock()
    mutex.acquire
    mutex.release
    
    #t1.join()
    #t2.join()

    time.sleep(20)
    print("ending program")



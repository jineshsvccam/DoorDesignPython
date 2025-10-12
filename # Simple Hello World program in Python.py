import ezdxf
def draw_rectangle(width, height, filename="rectangle.dxf"):
    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()
    # Draw rectangle using 4 lines
    msp.add_line((0, 0), (width, 0))
    msp.add_line((width, 0), (width, height))
    msp.add_line((width, height), (0, height))
    msp.add_line((0, height), (0, 0))
    doc.saveas(filename)
    print(f"Rectangle saved as {filename}")
import turtle
def draw_circle(radius):
    t = turtle.Turtle()
    t.circle(radius)
    turtle.done()
def add_numbers(a, b):
    return a + b

def print_fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        print(a, end=' ')
        a, b = b, a + b
    print()  # for newline

def main():
    num1 = 5  # dummy number
    num2 = 7  # dummy number
    result = add_numbers(num1, num2)
    print(f"The sum of {num1} and {num2} is {result}")

    print("Fibonacci series up to 10 terms:")
    print_fibonacci(10)

    print("Drawing a circle with radius 100...")
    draw_circle(100)

    print("Drawing a rectangle 200x100 and saving as DXF...")
    draw_rectangle(200, 100)

if __name__ == "__main__":
    main()
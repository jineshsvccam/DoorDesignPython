"""Inspect the LinearDimension renderer returned by DimStyleOverride.get_renderer()."""
import ezdxf
from ezdxf.filemanagement import new
from collections.abc import Iterable


def main():
    print("ezdxf version:", getattr(ezdxf, "__version__", "unknown"))
    doc = new(dxfversion="R2010")
    msp = doc.modelspace()
    p1 = (0,0)
    p2 = (200,0)
    dim = msp.add_linear_dim(base=(0,0), p1=p1, p2=p2, angle=0)
    try:
        renderer = dim.get_renderer()
    except Exception as e:
        print("get_renderer() raised:", e)
        return
    print("renderer type:", type(renderer))
    print("renderer dir:")
    rd = dir(renderer)
    print([r for r in rd if not r.startswith('_')])

    # check for common methods
    for name in ('virtual_entities', 'entities', 'entity_factory', 'render', 'build', 'compile', 'get_entities'):
        print(name, callable(getattr(renderer, name, None)))

    # try calling virtual_entities if exists
    vf = getattr(renderer, 'virtual_entities', None)
    if callable(vf):
        try:
            result = vf()
            if isinstance(result, Iterable):
                items = list(result)
            else:
                items = [result] if result is not None else []
            print('virtual_entities count:', len(items))
            for i, it in enumerate(items[:10]):
                try:
                    f = getattr(it, "dxftype", None)
                    if callable(f):
                        try:
                            print(i, f())
                        except Exception:
                            print(i, type(it))
                    else:
                        print(i, type(it))
                except Exception:
                    print(i, type(it))
        except Exception as e:
            print('virtual_entities() raised:', e)
    # Try rendering and inspect common properties that may contain entity data
    # Try calling render with modelspace as the block target
    try:
        before = len(list(msp))
        res = renderer.render(msp)
        after = len(list(msp))
        print('renderer.render(msp) returned type:', type(res), 'msp before/after:', before, after)
    except Exception as e:
        print('renderer.render(msp) raised:', e)

    for name in ('geometry', 'measurement', 'dimension_line', 'extension_lines', 'arrows'):
        val = getattr(renderer, name, None)
        print(name, '->', type(val))
        try:
            if val is not None and hasattr(val, '__len__'):
                print('  len =', len(val))
        except Exception:
            pass
        # if it's iterable, show element types
        try:
            if val is not None and hasattr(val, '__iter__') and not isinstance(val, (str, bytes)):
                items = list(val)
                for i, item in enumerate(items[:5]):
                    print(f'   [{i}] ->', type(item))
        except Exception as e:
            print('  iter inspection failed:', e)


if __name__ == '__main__':
    main()

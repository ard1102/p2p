import json
import argparse
import os

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except Exception:
    matplotlib = None
    plt = None

def load_results(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def plot_throughput(input_path, output_path):
    data = load_results(input_path)
    levels = data.get('levels', [])
    throughputs = [data['summaries'][str(l)]['throughput_bytes_per_sec'] for l in levels]

    if matplotlib and plt:
        plt.figure(figsize=(6,4))
        plt.plot(levels, throughputs, marker='o')
        plt.title('Strong Scaling: Throughput vs Concurrency')
        plt.xlabel('Concurrency (threads)')
        plt.ylabel('Throughput (bytes/sec)')
        plt.grid(True, linestyle='--', alpha=0.5)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, bbox_inches='tight')
        print(json.dumps({'plot': output_path, 'levels': levels, 'throughputs': throughputs}, indent=2))
        return True

    # Fallback: write CSV
    csv_path = os.path.splitext(output_path)[0] + '.csv'
    lines = ['concurrency,throughput_bytes_per_sec']
    for l, t in zip(levels, throughputs):
        lines.append(f"{l},{t if t is not None else ''}")
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(json.dumps({'csv': csv_path, 'levels': levels, 'throughputs': throughputs}, indent=2))
    return False


def main():
    parser = argparse.ArgumentParser(description='Plot throughput vs concurrency from strong scaling sweep')
    parser.add_argument('--input', default=os.path.join('evaluation', 'results', 'strong_scaling_sweep.json'))
    parser.add_argument('--output', default=os.path.join('evaluation', 'results', 'strong_throughput.png'))
    args = parser.parse_args()
    plot_throughput(args.input, args.output)

if __name__ == '__main__':
    main()
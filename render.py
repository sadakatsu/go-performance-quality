from mako.template import Template

from common import get_filename_core, render_html, ImageData


def render_table(
    renders_directory,
    analysis_filename,
    black_name,
    white_name,
    winner,
    scored_performances,
    black_summary,
    white_summary
) -> ImageData:
    filename_core = get_filename_core(analysis_filename)
    image_filename = f'{renders_directory}/{filename_core}.png'

    if winner == 'B':
        black_result = 'W'
        black_result_class = 'win'
        white_result = 'L'
        white_result_class = 'loss'
    elif winner == 'W':
        black_result = 'L'
        black_result_class = 'loss'
        white_result = 'W'
        white_result_class = 'win'
    else:
        black_result = '-'
        black_result_class = 'neither'
        white_result = '-'
        white_result_class = 'neither'

    mako_template = Template(_template)
    html = mako_template.render(
        black_accuracy=black_summary['accuracy'],
        black_best=black_summary['best_move'],
        black_match=black_summary['match'],
        black_name=black_name,
        black_quality=scored_performances['B']['actual'],
        black_result=black_result,
        black_result_class=black_result_class,
        black_simplicity=scored_performances['B']['expected'],
        black_summary=black_summary,
        game_quality=scored_performances['Game']['actual'],
        game_simplicity=scored_performances['Game']['expected'],
        white_accuracy=white_summary['accuracy'],
        white_best=white_summary['best_move'],
        white_match=white_summary['match'],
        white_name=white_name,
        white_quality=scored_performances['W']['actual'],
        white_result=white_result,
        white_result_class=white_result_class,
        white_simplicity=scored_performances['W']['expected'],
        white_summary=white_summary
    )

    size = render_html(html, image_filename)
    return ImageData(image_filename, size[0], size[1])


_template = '''
<%!
import numpy as np

def determine_percentile_style(percentile):
    if percentile == 5:
        return 'border-top: 2px solid black;'
    elif percentile == 25:
        return 'border-top: 1px solid black;'
    elif percentile == 50:
        return 'border-bottom: 1px dashed black; border-top: 1px dashed black;'
    elif percentile == 75:
        return 'border-bottom: 1px solid black;'
    elif percentile == 95:
        return 'border-bottom: 2px solid black;'
    else:
        return ''

def render_percentile(value):
    if int(value) == value:
        return str(int(value))
    else:
        return f'{value:0.2f}'

def determine_mistake_style(value, maximum):
    if value <= 3:
        perform_calculation = lambda x: calculate_gradient_color(value, 0, 3, x, 255)
        r = perform_calculation(90)
        g = perform_calculation(138)
        b = perform_calculation(198)
    else:
        perform_calculation = lambda x: calculate_gradient_color(value, 3, maximum, 255, x)
        r = perform_calculation(248)
        g = perform_calculation(105)
        b = perform_calculation(107)
    
    return f'background-color: rgb({r}, {g}, {b});'

def calculate_gradient_color(value, low, high, low_component, high_component):
    progress = (value - low) / (high - low)
    length = high_component - low_component
    return round(length * progress + low_component)

def create_gradient_function(minimum, minimum_color, middle, middle_color, maximum, maximum_color):
    def generated(value):
        value = float(value)
        if value <= minimum:
            r, g, b = minimum_color
        elif value >= maximum:
            r, g, b = maximum_color
        elif value < middle:
            perform_calculation = lambda x, y: calculate_gradient_color(value, minimum, middle, x, y)
            r = perform_calculation(minimum_color[0], middle_color[0])
            g = perform_calculation(minimum_color[1], middle_color[1])
            b = perform_calculation(minimum_color[2], middle_color[2])
        else:
            perform_calculation = lambda x, y: calculate_gradient_color(value, middle, maximum, x, y)
            r = perform_calculation(middle_color[0], maximum_color[0])
            g = perform_calculation(middle_color[1], maximum_color[1])
            b = perform_calculation(middle_color[2], maximum_color[2])
        return f'background-color: rgb({r}, {g}, {b});'
    return generated

determine_quality_style = create_gradient_function(
    0,
    (248, 105, 107),
    50,
    (255, 235, 132),
    100,
    (99, 190, 123)
)

determine_moves_style = create_gradient_function(
    17,
    (248, 105, 107),
    95,
    (255, 255, 255),
    174,
    (99, 190, 123)
)

determine_p_mistake_style = create_gradient_function(
    0,
    (99, 190, 123),
    0.519,
    (255, 235, 132),
    1,
    (248, 105, 107),
)

determine_loss_total_style = create_gradient_function(
    0,
    (99, 190, 123),
    187,
    (255, 235, 132),
    634,
    (248, 105, 107),
)

determine_loss_mean_style = create_gradient_function(
    0,
    (99, 190, 123),
    2.056,
    (255, 235, 132),
    6.392,
    (248, 105, 107),
)

determine_loss_std_dev_style = create_gradient_function(
    0,
    (99, 190, 123),
    3.163,
    (255, 235, 132),
    9.207,
    (248, 105, 107),
)
%>
<%
maximum = max(np.max(black_summary['timeline']), np.max(white_summary['timeline']))
%>
<%def name="print_neat_float(x)">
    ${f'{x:0.3f}'}
</%def>
<%def name="print_neat_percentage(x)">
    ${f'{x*100:0.1f}%'}
</%def>

<!DOCTYPE html>
<html>
    <head>
        <style>
            body {
                font-family: Calibri, sans-serif;
            }
            
            table {
                border-collapse: collapse;
            }
            
            tr:last-child {
                border-bottom: 2px solid black;
            }
        
            td, th {
                background-color: white;
                color: black;
                padding: 5px;
                text-align: center;
            }
            
            td:last-child, th:last-child {
                border-right: 2px solid black;
            }
            
            .black {
                color: white;
                background-color: black;
                border-bottom: 2px solid black;
                border-left: 2px solid black;
                border-right: 1px solid black;
                border-top: 2px solid black;
            }
            
            .label {
                border-left: 2px solid black;
                border-right: 2px solid black;
                font-weight: bold;
                text-align: left;
            }
            
            .loss {
                color: black;
                background-color: red;
            }
            
            .mistake:first-child, .percentile:first-child {
                border-top: 2px solid black;
            }
            
            .middle {
                border-right: 1px solid black;
            }
            
            .neither {
                background-color: #ffcc33
            }
            
            .overall-callout {
                border-bottom: 1px solid black;
                border-top: 1px solid black;
            }
            
            .split {
                border-bottom: 1px solid black;
            }
            
            .void {
                background-color: rgba(0, 0, 0, 0);
                border: 0px solid black !important;
            }
            
            .white {
                color: black;
                background-color: white;
                border-bottom: 2px solid black;
                border-left: 1px solid black;
                border-right: 2px solid black;
                border-top: 2px solid black;
            }
            
            .win {
                color: white;
                background-color: #00b050;
            }
        </style>
    </head>
    <body>
        <table>
            <thead>
                <tr>
                    <th class="void"></th>
                    <th class="black middle">${black_name}</th>
                    <th class="white">${white_name}</th>
                </tr>
            </thead>
            <tbody>
                <tr class="split">
                    <td class="label">Result</td>
                    <td class="${black_result_class} middle">${black_result}</td>
                    <td class="${white_result_class}">${white_result}</td>
                </tr>
                <tr>
                    <td class="label">Game Quality</td>
                    <td class="middle" colspan="2" style="${determine_quality_style(game_quality)}">
                        ${print_neat_float(game_quality)}
                    </td>
                </tr>
                <tr class="split">
                    <td class="label">Game Simplicity</td>
                    <td class="middle" colspan="2" style="${determine_quality_style(game_simplicity)}">
                        ${print_neat_float(game_simplicity)}
                    </td>
                </tr>
                <tr>
                    <td class="label">Play Quality</td>
                    <td class="middle" style="${determine_quality_style(black_quality)}">
                        ${print_neat_float(black_quality)}
                    </td>
                    <td style="${determine_quality_style(white_quality)}">
                        ${print_neat_float(white_quality)}
                    </td>
                </tr>
                <tr>
                    <td class="label">Simplicity</td>
                    <td class="middle" style="${determine_quality_style(black_simplicity)}">
                        ${print_neat_float(black_simplicity)}
                    </td>
                    <td style="${determine_quality_style(white_simplicity)}">
                        ${print_neat_float(white_simplicity)}
                    </td>
                </tr>
                
                <tr>
                    <td class="label">Accuracy</td>
                    <td class="middle" style="${determine_quality_style(black_accuracy*100)}">
                        ${print_neat_percentage(black_accuracy)}
                    </td>
                    <td style="${determine_quality_style(white_accuracy*100)}">
                        ${print_neat_percentage(white_accuracy)}
                    </td>
                </tr>
                
                <tr>
                    <td class="label">Best Move %</td>
                    <td class="middle" style="${determine_quality_style(black_best*100)}">
                        ${print_neat_percentage(black_best)}
                    </td>
                    <td style="${determine_quality_style(white_best*100)}">
                        ${print_neat_percentage(white_best)}
                    </td>
                </tr>
                
                <tr class="split">
                    <td class="label">Match %</td>
                    <td class="middle" style="${determine_quality_style(black_match*100)}">
                        ${print_neat_percentage(black_match)}
                    </td>
                    <td style="${determine_quality_style(white_match*100)}">
                        ${print_neat_percentage(white_match)}
                    </td>
                </tr>
                
                
                <tr>
                    <td class="label">Moves</td>
                    <td class="middle" style="${determine_moves_style(black_summary['moves'])}">
                        ${black_summary['moves']}
                    </td>
                    <td style="${determine_moves_style(white_summary['moves'])}">
                        ${white_summary['moves']}
                    </td>
                </tr>
                <tr>
                    <td class="label">Mistakes</td>
                    <td class="middle" style="${determine_p_mistake_style(black_summary['p(mistake)'])}">
                        ${black_summary['mistakes']}
                    </td>
                    <td style="${determine_p_mistake_style(black_summary['p(mistake)'])}">
                        ${white_summary['mistakes']}
                    </td>
                </tr>
                <tr>
                    <%
                    black_p_mistake_actual = black_summary['p(mistake)']
                    white_p_mistake_actual = white_summary['p(mistake)']
                    %>
                    <td class="label">p(Mistake)</td>
                    <td class="middle" style="${determine_p_mistake_style(black_summary['p(mistake)'])}">
                        ${print_neat_float(black_p_mistake_actual)}
                    </td>
                    <td style="${determine_p_mistake_style(black_summary['p(mistake)'])}">
                        ${print_neat_float(white_p_mistake_actual)}
                    </td>
                </tr>
                <tr>
                    <td class="label">Loss Total</td>
                    <td class="middle" style="${determine_loss_total_style(black_summary['loss_total'])}">
                        ${black_summary['loss_total']}
                    </td>
                    <td class="middle" style="${determine_loss_total_style(white_summary['loss_total'])}">
                        ${white_summary['loss_total']}
                    </td>
                </tr>
                <tr>
                    <td class="label">Loss Mean</td>
                    <td class="middle" style="${determine_loss_mean_style(black_summary['loss_mean'])}">
                        ${print_neat_float(black_summary['loss_mean'])}
                    </td>
                    <td class="middle" style="${determine_loss_mean_style(white_summary['loss_mean'])}">
                        ${print_neat_float(white_summary['loss_mean'])}
                    </td>
                </tr>
                <tr>
                    <td class="label">Loss Std. Dev.</td>
                    <td class="middle" style="${determine_loss_std_dev_style(black_summary['loss_std_dev'])}">
                        ${print_neat_float(black_summary['loss_std_dev'])}
                    </td>
                    <td class="middle" style="${determine_loss_std_dev_style(white_summary['loss_std_dev'])}">
                        ${print_neat_float(white_summary['loss_std_dev'])}
                    </td>
                </tr>
                % for percentile in range(5, 100, 5):
                <tr style="${determine_percentile_style(percentile)}">
                    <td class="label">Percentile: ${percentile}</td>
                    <%
                    p = np.percentile(black_summary['timeline'], percentile)
                    %>
                    <td class="middle" style="${determine_mistake_style(p, maximum)}">
                        ${render_percentile(p)}
                    </td>
                    <%
                    p = np.percentile(white_summary['timeline'], percentile)
                    %>
                    <td style="${determine_mistake_style(p, maximum)}">
                        ${render_percentile(p)}
                    </td>
                </tr>
                % endfor
                <%
                black_worst = sorted(black_summary['timeline'], reverse=True)
                white_worst = sorted(white_summary['timeline'], reverse=True)
                %>
                % for index in range(10):
                <tr>
                    <td class="label">Worst Move #${index + 1}</td>
                    <td class="middle" style="${determine_mistake_style(black_worst[index], maximum)}">
                        ${black_worst[index]}
                    </td>
                    <td style="${determine_mistake_style(white_worst[index], maximum)}">
                        ${white_worst[index]}
                    </td>
                </tr>
                % endfor
            </tbody>
        </table>
    </body>
</html>
'''
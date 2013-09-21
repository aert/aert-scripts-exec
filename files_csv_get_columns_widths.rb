
file_in = '<HERE-CSV-FILE-PATH>'

lines = IO.readlines(file_in)

if lines.length < 1
    puts "No data in file !"
    return
end

cols = lines[0].split(';')
nbcols = cols.length
puts "Nb cols : #{nbcols}"

i = 0
total = 0
cols.each do | c|
    i = i + 1
    total += c.size
    puts "Col #{i} : " + c.size.to_s
end

puts ">>> Total : #{total} car."

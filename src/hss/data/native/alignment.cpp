#include <algorithm>
#include <codecvt>
#include <fstream>
#include <filesystem>
#include <iostream>
#include <locale>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using Text = std::u32string;
struct Edit { char op; char32_t a, b; };
std::wstring_convert<std::codecvt_utf8<char32_t>, char32_t> utf8;

Text read(const std::filesystem::path& path) {
    std::ifstream file(path, std::ios::binary);
    if (!file) throw std::runtime_error("Cannot open " + path.u8string());
    std::ostringstream bytes; bytes << file.rdbuf();
    return utf8.from_bytes(bytes.str());
}

std::string quoted(const Text& value) {
    std::ostringstream result; result << '"';
    for (unsigned char c : utf8.to_bytes(value)) {
        if (c == '"' || c == '\\') result << '\\' << c;
        else if (c < 32) {
            const char* digits = "0123456789abcdef";
            result << "\\u00" << digits[c >> 4] << digits[c & 15];
        } else result << c;
    }
    result << '"'; return result.str();
}

std::vector<size_t> costs(const Text& a, const Text& b) {
    std::vector<size_t> previous(b.size()+1), current(b.size()+1);
    std::iota(previous.begin(), previous.end(), 0);
    for (size_t i=0; i<a.size(); ++i) {
        current[0] = i+1;
        for (size_t j=0; j<b.size(); ++j)
            current[j+1] = std::min({previous[j+1]+1, current[j]+1, previous[j]+(a[i]!=b[j])});
        previous.swap(current);
    }
    return previous;
}

void align(const Text& a, const Text& b, std::vector<Edit>& output) {
    if (a.empty()) { for (auto c:b) output.push_back({'I',0,c}); return; }
    if (b.empty()) { for (auto c:a) output.push_back({'D',c,0}); return; }
    if (a.size()==1 || b.size()==1) {
        std::vector<std::vector<size_t>> d(a.size()+1,std::vector<size_t>(b.size()+1));
        for (size_t i=0;i<=a.size();++i) d[i][0]=i;
        for (size_t j=0;j<=b.size();++j) d[0][j]=j;
        for(size_t i=1;i<=a.size();++i) for(size_t j=1;j<=b.size();++j)
            d[i][j]=std::min({d[i-1][j]+1,d[i][j-1]+1,d[i-1][j-1]+(a[i-1]!=b[j-1])});
        size_t i=a.size(),j=b.size(); std::vector<Edit> reversed;
        while(i || j) {
            if(i && j && d[i][j]==d[i-1][j-1]+(a[i-1]!=b[j-1])) {
                reversed.push_back({a[i-1]==b[j-1]?'E':'R',a[i-1],b[j-1]}); --i;--j;
            } else if(i && d[i][j]==d[i-1][j]+1) { reversed.push_back({'D',a[--i],0}); }
            else { reversed.push_back({'I',0,b[--j]}); }
        }
        output.insert(output.end(),reversed.rbegin(),reversed.rend()); return;
    }
    const size_t middle=a.size()/2;
    size_t split=0;
    {
        auto forward=costs(a.substr(0,middle),b);
        Text reverse_a=a.substr(middle),reverse_b=b;
        std::reverse(reverse_a.begin(),reverse_a.end());std::reverse(reverse_b.begin(),reverse_b.end());
        auto backward=costs(reverse_a,reverse_b);
        size_t best=forward[0]+backward[b.size()];
        for(size_t j=1;j<=b.size();++j) if(forward[j]+backward[b.size()-j]<best) {
            best=forward[j]+backward[b.size()-j];split=j;
        }
    }
    align(a.substr(0,middle),b.substr(0,split),output);
    align(a.substr(middle),b.substr(split),output);
}

int run(const std::vector<std::filesystem::path>& args) {
    try {
        if(args.size()==2 && args[1]=="--version") { std::cout<<"hss-align\n";return 0; }
        if(args.size()!=3) throw std::runtime_error("Usage: hss-align LEFT.txt RIGHT.txt");
        const auto a=read(args[1]),b=read(args[2]); std::vector<Edit> edits;align(a,b,edits);
        size_t distance=0;for(auto e:edits) distance+=e.op!='E';
        std::cout<<"{\"distance\":"<<distance<<",\"left_characters\":"<<a.size()<<",\"right_characters\":"<<b.size()<<",\"segments\":[";
        size_t i=0,j=0,k=0;bool first=true;
        while(k<edits.size()) {
            char op=edits[k].op;const size_t begin_i=i,begin_j=j;
            while(k<edits.size() && edits[k].op==op) { if(op!='I')++i;if(op!='D')++j;++k; }
            if(!first)std::cout<<',';first=false;
            const char* name=op=='E'?"equal":op=='R'?"replace":op=='I'?"insert":"delete";
            std::cout<<"{\"operation\":\""<<name<<"\",\"left_start\":"<<begin_i<<",\"left_end\":"<<i
                <<",\"right_start\":"<<begin_j<<",\"right_end\":"<<j<<",\"left\":"<<quoted(a.substr(begin_i,i-begin_i))
                <<",\"right\":"<<quoted(b.substr(begin_j,j-begin_j))<<'}';
        }
        std::cout<<"]}\n";return 0;
    } catch(const std::exception& error) { std::cerr<<error.what()<<'\n';return 1; }
}

#ifdef _WIN32
int wmain(int argc, wchar_t** argv) {
#else
int main(int argc, char** argv) {
#endif
    std::vector<std::filesystem::path> args;
    for (int i=0;i<argc;++i) args.emplace_back(argv[i]);
    return run(args);
}
